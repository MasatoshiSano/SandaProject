from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import jpholiday
from datetime import datetime, time, timedelta
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class Line(models.Model):
    """生産ライン"""
    name = models.CharField('ライン名', max_length=100)
    description = models.TextField('説明', blank=True)
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = 'ライン'
        verbose_name_plural = 'ライン'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserLineAccess(models.Model):
    """ユーザーとラインのアクセス管理"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='ユーザー')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='ライン')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    class Meta:
        verbose_name = 'ユーザーラインアクセス'
        verbose_name_plural = 'ユーザーラインアクセス'
        unique_together = ['user', 'line']

    def __str__(self):
        return f'{self.user.username} - {self.line.name}'


class Machine(models.Model):
    """設備"""
    name = models.CharField('設備名', max_length=100)
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='ライン')
    description = models.TextField('説明', blank=True)
    is_active = models.BooleanField('有効', default=True)
    is_production_active = models.BooleanField('生産稼働中', default=False, help_text='この設備が現在生産稼働中かを示すフラグ')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '設備'
        verbose_name_plural = '設備'
        ordering = ['line', 'name']

    def __str__(self):
        return f'{self.line.name} - {self.name}'


class Category(models.Model):
    """機種カテゴリ"""
    name = models.CharField('カテゴリ名', max_length=100, unique=True)
    description = models.TextField('説明', blank=True)
    color = models.CharField('色', max_length=7, default='#007bff', help_text='HEX形式 (#RRGGBB)')
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = 'カテゴリ'
        verbose_name_plural = 'カテゴリ'
        ordering = ['name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    """機種タグ"""
    name = models.CharField('タグ名', max_length=50, unique=True)
    description = models.TextField('説明', blank=True)
    color = models.CharField('色', max_length=7, default='#6c757d', help_text='HEX形式 (#RRGGBB)')
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = 'タグ'
        verbose_name_plural = 'タグ'
        ordering = ['name']

    def __str__(self):
        return self.name


class Part(models.Model):
    """機種"""
    name = models.CharField('機種名', max_length=100, unique=True)
    part_number = models.CharField('品番', max_length=50, blank=True, unique=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='カテゴリ')
    tags = models.ManyToManyField(Tag, blank=True, verbose_name='タグ')
    target_pph = models.PositiveIntegerField('目標PPH', validators=[MinValueValidator(1)],null=True,blank=True)
    cycle_time = models.FloatField('サイクルタイム(秒)', editable=False,null=True,blank=True)
    description = models.TextField('説明', blank=True)
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '機種'
        verbose_name_plural = '機種'
        ordering = ['name']

    def save(self, *args, **kwargs):
        # サイクルタイム = 3600 ÷ 目標PPH
        self.cycle_time = 3600 / self.target_pph
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Plan(models.Model):
    """生産計画"""
    date = models.DateField('日付')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='ライン')
    part = models.ForeignKey(Part, on_delete=models.CASCADE, verbose_name='機種')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, verbose_name='機械', default=1)
    start_time = models.TimeField('開始時間', default=time(8, 0))
    end_time = models.TimeField('終了時間', default=time(17, 0))
    planned_quantity = models.PositiveIntegerField('計画数量', validators=[MinValueValidator(1)], default=1)
    sequence = models.PositiveIntegerField('順番', default=1)
    notes = models.TextField('備考', blank=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '生産計画'
        verbose_name_plural = '生産計画'
        ordering = ['date', 'line', 'start_time']
        unique_together = ['date', 'line', 'sequence']

    def __str__(self):
        return f'{self.date.strftime("%m/%d")} {self.start_time.strftime("%H:%M")}-{self.end_time.strftime("%H:%M")} [{self.line.name}] {self.part.name} ({self.planned_quantity}個)'
    
    @property
    def duration_minutes(self):
        """計画時間を分単位で返す"""
        start_datetime = datetime.combine(self.date, self.start_time)
        end_datetime = datetime.combine(self.date, self.end_time)
        return int((end_datetime - start_datetime).total_seconds() / 60)
    
    @property
    def actual_quantity(self):
        """実績数量を返す（同日・同ライン・同機種の実績を集計）"""
        from datetime import datetime, time
        start_datetime = datetime.combine(self.date, time.min)
        end_datetime = datetime.combine(self.date, time.max)
        
        return Result.objects.filter(
            line=self.line,
            part=self.part,
            judgment='OK',
            timestamp__range=(start_datetime, end_datetime)
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def achievement_rate(self):
        """達成率を返す"""
        if self.planned_quantity == 0:
            return 0
        return (self.actual_quantity / self.planned_quantity) * 100


class Result(models.Model):
    """実績"""
    JUDGMENT_CHOICES = [
        ('OK', 'OK'),
        ('NG', 'NG'),
    ]

    quantity = models.PositiveIntegerField('数量', default=1, validators=[MinValueValidator(1)])
    
    # 実績は計画に依存しない独立したデータ（文字列として保存）
    line = models.CharField('ライン', max_length=100, default='', blank=True, null=True)
    machine = models.CharField('設備', max_length=100, default='', blank=True, null=True)  
    part = models.CharField('機種', max_length=100, default='', blank=True, null=True)
    
    timestamp = models.DateTimeField('タイムスタンプ')
    serial_number = models.CharField('シリアル番号', max_length=100)
    judgment = models.CharField('判定', max_length=2, choices=JUDGMENT_CHOICES)
    notes = models.TextField('備考', blank=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    class Meta:
        verbose_name = '実績'
        verbose_name_plural = '実績'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.timestamp} - {self.line} - {self.part} - {self.serial_number}'


class WeeklyResultAggregation(models.Model):
    """週別分析用の実績集計テーブル"""
    JUDGMENT_CHOICES = [
        ('OK', 'OK'),
        ('NG', 'NG'),
    ]

    # 集計キー
    date = models.DateField('日付', db_index=True)
    line = models.CharField('ライン', max_length=100, db_index=True)
    machine = models.CharField('設備', max_length=100, blank=True, null=True)
    part = models.CharField('機種', max_length=100, db_index=True)
    judgment = models.CharField('判定', max_length=2, choices=JUDGMENT_CHOICES)
    
    # 集計値
    total_quantity = models.PositiveIntegerField('合計数量', default=0)
    result_count = models.PositiveIntegerField('実績件数', default=0)
    
    # メタデータ
    last_updated = models.DateTimeField('最終更新', auto_now=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    class Meta:
        verbose_name = '週別実績集計'
        verbose_name_plural = '週別実績集計'
        unique_together = ['date', 'line', 'machine', 'part', 'judgment']
        indexes = [
            models.Index(fields=['date', 'line']),
            models.Index(fields=['date', 'line', 'part']),
            models.Index(fields=['date', 'line', 'judgment']),
        ]
        ordering = ['-date', 'line', 'part']

    def __str__(self):
        return f'{self.date} - {self.line} - {self.part} - {self.judgment} ({self.total_quantity})'


class PartChangeDowntime(models.Model):
    """機種切替ダウンタイム"""
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='ライン')
    from_part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='change_from', verbose_name='切替前機種')
    to_part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='change_to', verbose_name='切替後機種')
    downtime_seconds = models.PositiveIntegerField('ダウンタイム(秒)', validators=[MinValueValidator(0)])
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '機種切替ダウンタイム'
        verbose_name_plural = '機種切替ダウンタイム'
        unique_together = ['line', 'from_part', 'to_part']

    def __str__(self):
        return f'{self.line.name}: {self.from_part.name} → {self.to_part.name} ({self.downtime_seconds}秒)'


class WorkCalendar(models.Model):
    """稼働カレンダー設定"""
    line = models.OneToOneField(Line, on_delete=models.CASCADE, verbose_name='ライン')
    work_start_time = models.TimeField('稼働開始時間', default=time(8, 30))
    morning_meeting_duration = models.PositiveIntegerField('朝礼時間(分)', default=15)
    break_times = models.JSONField('休憩時間', default=list, help_text='[{"start": "10:45", "end": "11:00"}, ...]')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '稼働カレンダー'
        verbose_name_plural = '稼働カレンダー'

    def __str__(self):
        return f'{self.line.name} - 稼働カレンダー'

    def get_default_break_times(self):
        """デフォルトの休憩時間を返す"""
        return [
            {"start": "10:45", "end": "11:00"},
            {"start": "12:00", "end": "12:45"},
            {"start": "15:00", "end": "15:15"},
            {"start": "17:00", "end": "17:15"},
        ]

    def save(self, *args, **kwargs):
        if not self.break_times:
            self.break_times = self.get_default_break_times()
        super().save(*args, **kwargs)


class WorkingDay(models.Model):
    """稼働日管理"""
    date = models.DateField('日付', unique=True)
    is_working = models.BooleanField('稼働日', default=True)
    is_holiday = models.BooleanField('祝日', default=False)
    holiday_name = models.CharField('祝日名', max_length=100, blank=True, null=True)
    start_time = models.TimeField('開始時間', null=True, blank=True)
    end_time = models.TimeField('終了時間', null=True, blank=True)
    break_minutes = models.PositiveIntegerField('休憩時間(分)', default=0)
    description = models.CharField('説明', max_length=200, blank=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '稼働日'
        verbose_name_plural = '稼働日'
        ordering = ['-date']

    def __str__(self):
        status = '稼働' if self.is_working else '非稼働'
        return f'{self.date} ({status})'

    @classmethod
    def is_working_day(cls, date):
        """指定日が稼働日かどうかを判定"""
        try:
            working_day = cls.objects.get(date=date)
            return working_day.is_working
        except cls.DoesNotExist:
            # 土日祝日は非稼働
            if date.weekday() >= 5:  # 土曜日(5), 日曜日(6)
                return False
            if jpholiday.is_holiday(date):
                return False
            return True


class DashboardCardSetting(models.Model):
    """ダッシュボードカード表示設定"""
    name = models.CharField('カード名', max_length=100, unique=True)
    is_visible = models.BooleanField('表示', default=True)
    order = models.PositiveIntegerField('表示順', default=0)
    alert_threshold_yellow = models.FloatField('黄色アラート閾値(%)', default=80.0)
    alert_threshold_red = models.FloatField('赤色アラート閾値(%)', default=80.0)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = 'ダッシュボードカード設定'
        verbose_name_plural = 'ダッシュボードカード設定'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class PlannedHourlyProduction(models.Model):
    """計画時間別生産数（計画PPH）"""
    date = models.DateField('日付')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='ライン')
    part = models.ForeignKey(Part, on_delete=models.CASCADE, verbose_name='機種')
    hour = models.PositiveIntegerField('時間帯', help_text='0-47（0-23=当日、24-47=翌日）')
    planned_quantity = models.PositiveIntegerField('計画数量', default=0)
    working_seconds = models.PositiveIntegerField('稼働秒数', default=0, help_text='休憩時間を除いた実稼働秒数')
    production_events = models.JSONField('生産イベント', default=list, help_text='この時間帯の生産イベント詳細')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '計画時間別生産数'
        verbose_name_plural = '計画時間別生産数'
        ordering = ['date', 'line', 'hour']
        unique_together = ['date', 'line', 'part', 'hour']
        indexes = [
            models.Index(fields=['date', 'line']),
            models.Index(fields=['date', 'line', 'hour']),
        ]

    def __str__(self):
        day_type = "当日" if self.hour < 24 else "翌日"
        actual_hour = self.hour if self.hour < 24 else self.hour - 24
        return f'{self.date.strftime("%m/%d")} [{self.line.name}] {actual_hour:02d}時台({day_type}) {self.part.name} ({self.planned_quantity}個)'
    
    @property
    def actual_hour(self):
        """実際の時間（0-23）"""
        return self.hour if self.hour < 24 else self.hour - 24
    
    @property
    def is_next_day(self):
        """翌日の時間帯かどうか"""
        return self.hour >= 24
    
    @property
    def planned_pph(self):
        """計画PPH（時間当たり生産数）"""
        return self.planned_quantity if self.working_seconds >= 3600 else 0


class UserPreference(models.Model):
    """ユーザー設定"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='ユーザー')
    last_selected_line = models.ForeignKey(Line, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='最後に選択したライン')
    theme = models.CharField('テーマ', max_length=10, choices=[('light', 'ライト'), ('dark', 'ダーク')], default='light')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = 'ユーザー設定'
        verbose_name_plural = 'ユーザー設定'

    def __str__(self):
        return f'{self.user.username} - 設定'


class ProductionForecastSettings(models.Model):
    """終了予測計算設定"""
    line = models.OneToOneField(Line, on_delete=models.CASCADE, verbose_name='ライン')
    calculation_interval_minutes = models.PositiveIntegerField(
        '計算間隔(分)', 
        default=15, 
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        verbose_name = '終了予測設定'
        verbose_name_plural = '終了予測設定'

    def __str__(self):
        return f'{self.line.name} - 予測設定 ({self.calculation_interval_minutes}分間隔)'


class ProductionForecast(models.Model):
    """生産終了予測"""
    line = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='ライン')
    target_date = models.DateField('対象日付')
    forecast_completion_time = models.TimeField('予測完了時刻', null=True, blank=True)
    calculation_timestamp = models.DateTimeField('計算実行時刻')
    current_production_rate = models.DecimalField(
        '現在の生産速度', max_digits=10, decimal_places=1, null=True, blank=True
    )
    total_planned_quantity = models.PositiveIntegerField('計画総数量', default=0)
    total_actual_quantity = models.PositiveIntegerField('実績総数量', default=0)
    is_delayed = models.BooleanField('遅延予測', default=False)
    confidence_level = models.PositiveIntegerField(
        '信頼度', default=0, 
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    is_next_day = models.BooleanField('翌日', default=False)
    error_message = models.TextField('エラーメッセージ', blank=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        verbose_name = '生産終了予測'
        verbose_name_plural = '生産終了予測'
        unique_together = ['line', 'target_date']
        ordering = ['-target_date', 'line']

    def __str__(self):
        completion_str = self.forecast_completion_time.strftime('%H:%M') if self.forecast_completion_time else '--:--'
        return f'{self.target_date} {self.line.name} - {completion_str}'


# シグナル設定
@receiver([post_save, post_delete], sender=Plan)
def recalculate_planned_pph(sender, instance, **kwargs):
    """計画の保存・削除時に計画PPHを再計算"""
    from .utils import calculate_planned_pph_for_date
    
    try:
        # 非同期で計算実行（重い処理のため）
        from django.db import transaction
        
        def run_calculation():
            calculate_planned_pph_for_date(instance.line_id, instance.date)
        
        # トランザクション完了後に実行
        transaction.on_commit(run_calculation)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"計画PPH自動計算エラー: {e}")


# 週別分析パフォーマンス改善用シグナル
def retry_with_backoff(func, max_retries=3, base_delay=1):
    """
    指数バックオフでリトライを実行する関数
    
    Args:
        func: 実行する関数
        max_retries: 最大リトライ回数
        base_delay: 基本遅延時間（秒）
    """
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"最大リトライ回数に達しました: {e}")
                raise
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"リトライ {attempt + 1}/{max_retries + 1}: {delay}秒後に再試行 - {e}")
            time.sleep(delay)


@receiver(post_save, sender=Result)
def update_aggregation_on_result_save(sender, instance, created, **kwargs):
    """実績データ保存時の集計更新（エラーハンドリング強化版）"""
    from .services import AggregationService
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 非同期で集計更新を実行
        from django.db import transaction
        
        def run_aggregation_update():
            def update_with_retry():
                service = AggregationService()
                service.incremental_update(instance)
                return True
            
            try:
                # リトライ機能付きで実行
                retry_with_backoff(update_with_retry, max_retries=2, base_delay=0.5)
                logger.info(f"実績保存時集計更新完了: {instance.id}")
                
                # WebSocket通知を送信
                send_aggregation_update_notification(instance)
                
            except Exception as e:
                logger.error(f"実績保存時集計更新エラー（リトライ後）: {e}")
                
                # フォールバック: 該当日の完全再集計をスケジュール
                try:
                    from .utils import schedule_full_reaggregation
                    target_date = instance.timestamp.date()
                    line_name = instance.line
                    
                    # ライン名からライン ID を取得
                    try:
                        line = Line.objects.get(name=line_name)
                        schedule_full_reaggregation(line.id, target_date)
                        logger.info(f"フォールバック: 完全再集計をスケジュール - ライン: {line_name}, 日付: {target_date}")
                    except Line.DoesNotExist:
                        logger.error(f"ライン '{line_name}' が見つかりません")
                        
                except Exception as fallback_error:
                    logger.error(f"フォールバック処理エラー: {fallback_error}")
        
        # トランザクション完了後に実行
        transaction.on_commit(run_aggregation_update)
        
    except Exception as e:
        logger.error(f"実績保存シグナルエラー: {e}")


@receiver(post_delete, sender=Result)
def update_aggregation_on_result_delete(sender, instance, **kwargs):
    """実績データ削除時の集計更新（エラーハンドリング強化版）"""
    from .services import AggregationService
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 非同期で集計削除を実行
        from django.db import transaction
        
        def run_aggregation_delete():
            def delete_with_retry():
                service = AggregationService()
                service.incremental_delete(instance)
                return True
            
            try:
                # リトライ機能付きで実行
                retry_with_backoff(delete_with_retry, max_retries=2, base_delay=0.5)
                logger.info(f"実績削除時集計更新完了: {instance.id}")
                
            except Exception as e:
                logger.error(f"実績削除時集計更新エラー（リトライ後）: {e}")
                
                # フォールバック: 該当日の完全再集計をスケジュール
                try:
                    from .utils import schedule_full_reaggregation
                    target_date = instance.timestamp.date()
                    line_name = instance.line
                    
                    # ライン名からライン ID を取得
                    try:
                        line = Line.objects.get(name=line_name)
                        schedule_full_reaggregation(line.id, target_date)
                        logger.info(f"フォールバック: 完全再集計をスケジュール - ライン: {line_name}, 日付: {target_date}")
                    except Line.DoesNotExist:
                        logger.error(f"ライン '{line_name}' が見つかりません")
                        
                except Exception as fallback_error:
                    logger.error(f"フォールバック処理エラー: {fallback_error}")
        
        # トランザクション完了後に実行
        transaction.on_commit(run_aggregation_delete)
        
    except Exception as e:
        logger.error(f"実績削除シグナルエラー: {e}")


class Feedback(models.Model):
    """フィードバック"""
    CATEGORY_CHOICES = [
        ('feature', '機能改善'),
        ('bug', 'バグ報告'),
        ('ui_ux', 'UI/UX改善'),
        ('other', 'その他'),
    ]
    
    PRIORITY_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
    ]

    STATUS_CHOICES = [
        ('new', '新規'),
        ('in_review', '確認中'),
        ('in_progress', '対応中'),
        ('completed', '完了'),
        ('rejected', '却下'),
    ]
    
    category = models.CharField('カテゴリ', max_length=10, choices=CATEGORY_CHOICES, default='other')
    priority = models.CharField('優先度', max_length=10, choices=PRIORITY_CHOICES, default='medium')
    description = models.TextField('詳細内容', default='')
    attachment = models.FileField('添付ファイル', upload_to='feedback_attachments/', blank=True, null=True)
    page_url = models.URLField('送信時のURL', blank=True)
    
    # メタ情報
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='送信者')
    status = models.CharField('ステータス', max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        verbose_name = 'フィードバック'
        verbose_name_plural = 'フィードバック'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_category_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


def send_aggregation_update_notification(result_instance):
    """集計更新のWebSocket通知を送信"""
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        
        # ライン情報を取得
        try:
            line = Line.objects.get(name=result_instance.line)
            line_id = line.id
        except Line.DoesNotExist:
            return
        
        # 通知データを準備
        notification_data = {
            'type': 'aggregation_update',
            'line_id': line_id,
            'line_name': result_instance.line,
            'date': result_instance.timestamp.date().isoformat(),
            'part': result_instance.part,
            'judgment': result_instance.judgment,
            'quantity': result_instance.quantity,
            'timestamp': result_instance.timestamp.isoformat()
        }
        
        # 週別分析コンシューマーに通知
        weekly_analysis_group = f'weekly_analysis_{line_id}'
        async_to_sync(channel_layer.group_send)(
            weekly_analysis_group,
            {
                'type': 'aggregation_update',
                'data': notification_data
            }
        )
        
        # 集計状況監視コンシューマーに通知
        async_to_sync(channel_layer.group_send)(
            'aggregation_status',
            {
                'type': 'aggregation_status_update',
                'data': {
                    'type': 'result_updated',
                    'line_name': result_instance.line,
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
        
        # ダッシュボードコンシューマーに通知（該当日のみ）
        target_date = result_instance.timestamp.date().isoformat()
        dashboard_group = f'dashboard_{line_id}_{target_date}'
        async_to_sync(channel_layer.group_send)(
            dashboard_group,
            {
                'type': 'dashboard_update',
                'data': {
                    'type': 'result_updated',
                    'result_data': notification_data
                }
            }
        )
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"WebSocket通知送信エラー: {e}")


def send_aggregation_status_notification(status_type, data):
    """集計状況の変更通知を送信"""
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        
        # 集計状況監視コンシューマーに通知
        async_to_sync(channel_layer.group_send)(
            'aggregation_status',
            {
                'type': 'aggregation_status_update',
                'data': {
                    'type': status_type,
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"集計状況通知送信エラー: {e}")


def send_weekly_analysis_update(line_id, start_date, end_date):
    """週別分析データの更新通知を送信"""
    try:
        from .services import WeeklyAnalysisService
        
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        
        # 更新されたデータを取得
        line = Line.objects.get(id=line_id)
        service = WeeklyAnalysisService()
        
        weekly_data = service.get_weekly_data(line.name, start_date, end_date)
        performance_metrics = service.get_performance_metrics(line.name, start_date, end_date)
        
        # 週別分析コンシューマーに通知
        weekly_analysis_group = f'weekly_analysis_{line_id}'
        async_to_sync(channel_layer.group_send)(
            weekly_analysis_group,
            {
                'type': 'weekly_analysis_update',
                'data': {
                    'line_name': line.name,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'weekly_data': weekly_data,
                    'performance_metrics': performance_metrics,
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"週別分析更新通知送信エラー: {e}")