from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
import jpholiday
from datetime import datetime, time, timedelta
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


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
