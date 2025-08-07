from datetime import datetime, timedelta, time
from django.db import models
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Sum
from django.utils import timezone
from .models import Plan, Result, WorkCalendar, WorkingDay, Part, PlannedHourlyProduction, PartChangeDowntime, Line, Machine
import jpholiday
from collections import defaultdict
import calendar
import logging
import hashlib

logger = logging.getLogger(__name__)


def generate_part_color(part_id, part_name=None):
    """機種IDベースで一意な色を生成する"""
    # 機種IDと名前を組み合わせてハッシュを生成
    hash_input = f"{part_id}_{part_name or ''}"
    hash_object = hashlib.md5(hash_input.encode())
    hex_hash = hash_object.hexdigest()
    
    # HSL色空間で色を生成（彩度・明度を固定して見やすい色にする）
    hue = int(hex_hash[:3], 16) % 360  # 0-359の色相
    saturation = 65 + (int(hex_hash[3:5], 16) % 25)  # 65-89%の彩度
    lightness = 45 + (int(hex_hash[5:7], 16) % 20)   # 45-64%の明度
    
    # HSLをRGBに変換
    def hsl_to_rgb(h, s, l):
        h = h / 360
        s = s / 100
        l = l / 100
        
        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p, q, t):
                if t < 0:
                    t += 1
                if t > 1:
                    t -= 1
                if t < 1/6:
                    return p + (q - p) * 6 * t
                if t < 1/2:
                    return q
                if t < 2/3:
                    return p + (q - p) * (2/3 - t) * 6
                return p
            
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return int(r * 255), int(g * 255), int(b * 255)
    
    r, g, b = hsl_to_rgb(hue, saturation, lightness)
    return f"#{r:02x}{g:02x}{b:02x}"


def get_count_target_machines(line_id):
    """ライン内のカウント対象設備を取得"""
    
    # ライン内のカウント対象設備を取得
    machines = Machine.objects.filter(
        line_id=line_id, 
        is_active=True,
        is_count_target=True
    ).order_by('name')
    
    logger.info(f"カウント対象設備: {[m.name for m in machines]}")
    return machines


def calculate_input_count(line_id, date_str):
    """
    投入数を計算する
    
    Args:
        line_id (int): ライン ID
        date_str (str): 日付文字列 (YYYY-MM-DD形式)
        
    Returns:
        int: 投入数（全判定を含む）
    """
    try:
        # 日付文字列を date に変換
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"無効な日付形式: {date_str}")
            return 0
        
        # Line オブジェクト取得
        try:
            line = Line.objects.get(id=line_id)
            line_name = line.name
        except Line.DoesNotExist:
            logger.error(f"ライン ID {line_id} が見つかりません")
            return 0
        
        # WorkCalendarからwork_start_timeを取得
        try:
            work_calendar = WorkCalendar.objects.get(line_id=line_id)
            work_start_time = work_calendar.work_start_time
        except WorkCalendar.DoesNotExist:
            logger.warning(f"ライン ID {line_id} のWorkCalendarが見つかりません。デフォルト値を使用します")
            work_start_time = time(8, 30)  # デフォルト値
        
        # 投入数対象設備を取得
        input_count_machines = Machine.objects.filter(
            line_id=line_id, 
            is_count_target=True,
            is_active=True
        )
        
        if not input_count_machines.exists():
            logger.info(f"ライン ID {line_id} に投入数対象設備がありません")
            return 0
        
        input_count_machine_names = [m.name for m in input_count_machines]
        logger.info(f"投入数対象設備: {input_count_machine_names}")
        
        # 時間期間を計算
        actual_work_start = datetime.combine(date, work_start_time)
        next_day_work_start = actual_work_start + timedelta(days=1)
        
        # Oracleテーブルのtimestampは文字列形式（YYYYMMDDhhmmss）
        start_str = actual_work_start.strftime('%Y%m%d%H%M%S')
        end_str = next_day_work_start.strftime('%Y%m%d%H%M%S')
        
        logger.info(f"投入数計算期間: {start_str} - {end_str}")
        
        # 投入数を計算（全判定を含む - OK/NG両方）
        input_results = Result.objects.filter(
            line=line_name,
            machine__in=input_count_machine_names,
            timestamp__gte=start_str,
            timestamp__lt=end_str,
            sta_no1='SAND'  # フィルタ条件
        )
        
        input_count = input_results.count()
        logger.info(f"投入数: {input_count}")
        
        return input_count
        
    except Exception as e:
        logger.error(f"投入数計算エラー: {e}")
        return 0


def get_dashboard_data(line_id, date_str):
    """ダッシュボード用のデータを取得"""
    # --- 1. Line オブジェクト／名称取得 ---
    line = get_object_or_404(Line, id=line_id)
    line_name = line.name

    # --- 2. 日付文字列を date に変換 ---
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = timezone.now().date()

    # --- 3. 計画(Plan)の取得 ---
    plans = Plan.objects.filter(line_id=line_id, date=date).order_by('sequence')

    # --- 4. カウント対象設備を特定 ---
    count_target_machines = get_count_target_machines(line_id)
    count_target_machine_names = [m.name for m in count_target_machines]
    
    # --- 5. 実績(Result)の取得（カウント対象設備のみ） ---
    # WorkCalendarからwork_start_timeを取得
    try:
        work_calendar = WorkCalendar.objects.get(line_id=line_id)
        work_start_time = work_calendar.work_start_time
        morning_meeting_duration = work_calendar.morning_meeting_duration
    except WorkCalendar.DoesNotExist:
        work_start_time = time(8, 30)  # デフォルト値
        morning_meeting_duration = 15
    
    # 実際の作業開始時刻（朝礼時間を考慮）
    actual_work_start = datetime.combine(date, work_start_time) + timedelta(minutes=morning_meeting_duration)
    # 翌日の作業開始時刻まで
    next_day_work_start = actual_work_start + timedelta(days=1)
    
    # Oracleテーブルのtimestampは文字列形式（YYYYMMDDhhmmss）
    start_str = actual_work_start.strftime('%Y%m%d%H%M%S')
    end_str = next_day_work_start.strftime('%Y%m%d%H%M%S')
    
    results = Result.objects.filter(
        line=line_name,
        machine__in=count_target_machine_names,  # カウント対象設備のみ
        timestamp__gte=start_str,
        timestamp__lt=end_str,  # 翌日の開始時刻未満
        judgment='1',  # Oracle形式（1=OK, 2=NG）
        sta_no1='SAND'  # フィルタ条件
    )
    # --- 5. 機種別データの集計 ---
    # キーは「機種名」の文字列
    part_data: dict[str, dict] = {}

    # 5-1. 計画数量を加算
    for plan in plans:
        pname = plan.part.name
        if pname not in part_data:
            part_data[pname] = {
                'name': pname,
                'planned': 0,
                'actual': 0,
                'achievement_rate': 0,
                'color': generate_part_color(plan.part.id, plan.part.name),
            }
        part_data[pname]['planned'] += plan.planned_quantity

    # 5-2. 実績数量を加算＆達成率計算
    for result in results:
        pname = result.part  # 文字列フィールドから機種名を取得
        # カラー取得のため、Part オブジェクトにフォールバック
        if pname not in part_data:
            try:
                part_obj = Part.objects.get(name=pname)
                color = generate_part_color(part_obj.id, part_obj.name)
            except Part.DoesNotExist:
                color = '#000000'
            part_data[pname] = {
                'name': pname,
                'planned': 0,
                'actual': 0,
                'achievement_rate': 0,
                'color': color,
            }
        # 数量を加算
        part_data[pname]['actual'] += result.quantity
        planned = part_data[pname]['planned']
        if planned > 0:
            part_data[pname]['achievement_rate'] = (
                part_data[pname]['actual'] / planned * 100
            )

    # --- 6. 時間別データ生成 ---
    hourly_data = generate_hourly_data_machine_based(
        line_id, date, plans, count_target_machines, results
    )

    # --- 7. 総計算＆残数 ---
    total_planned = sum(d['planned'] for d in part_data.values())
    total_actual  = sum(d['actual']  for d in part_data.values())
    achievement_rate = (
        total_actual / total_planned * 100 if total_planned else 0
    )
    remaining = max(0, total_planned - total_actual)

    # --- 8. 投入数計算 ---
    try:
        input_count = calculate_input_count(line_id, date_str)
    except Exception as e:
        logger.error(f"ダッシュボード投入数計算エラー: {e}")
        input_count = 0  # フォールバック値

    # --- 9. 結果返却 ---
    return {
        'parts': list(part_data.values()),
        'hourly': hourly_data,
        'total_planned': total_planned,
        'total_actual': total_actual,
        'input_count': input_count,
        'achievement_rate': achievement_rate,
        'remaining': remaining,
        'last_updated': timezone.now().isoformat(),
    }

def generate_hourly_data(line_id, date, plans, results):
    """時間別データを生成（機種別）- work_start_timeから1時間刻みで生成"""
    try:
        work_calendar = WorkCalendar.objects.get(line_id=line_id)
        work_start = work_calendar.work_start_time
        morning_meeting_duration = work_calendar.morning_meeting_duration
    except WorkCalendar.DoesNotExist:
        work_start = time(8, 30)
        morning_meeting_duration = 15
    
    hourly_data = []
    
    # work_start_timeから1時間刻みで24時間分のデータを生成
    for hour_index in range(24):
        # 実際の時間を計算（work_start_timeから1時間刻み）
        hour_start = datetime.combine(date, work_start) + timedelta(hours=hour_index)
        hour_end = hour_start + timedelta(hours=1)
        
        # 最初の時間帯の場合、朝礼時間を考慮して表示
        display_time = hour_start.strftime('%H:%M')
        if hour_index == 0:
            effective_start = hour_start + timedelta(minutes=morning_meeting_duration)
            display_time = f"{hour_start.strftime('%H:%M')}({effective_start.strftime('%H:%M')}~)"
        
        hour_data = {
            'hour': display_time,
            'total_planned': 0,
            'total_actual': 0,
            'parts': {}
        }
        
        # 新しい計画PPHデータから計画数を取得
        planned_productions = PlannedHourlyProduction.objects.filter(
            line_id=line_id,
            date=date,
            hour=hour_index  # work_start_timeからのオフセット
        )
        
        # 計画数を集計（機種別、ラインごと）
        for planned_prod in planned_productions:
            part_id = planned_prod.part_id
            part = planned_prod.part
            
            if part_id not in hour_data['parts']:
                hour_data['parts'][part_id] = {
                    'name': part.name,
                    'color': generate_part_color(part.id, part.name),
                    'planned': 0,
                    'actual': 0,
                }
            
            # ラインごとに集計されているので、そのまま加算
            hour_data['parts'][part_id]['planned'] += planned_prod.planned_quantity
            hour_data['total_planned'] += planned_prod.planned_quantity
        
        # 実績数を取得（機種別）
        # 最初の時間帯は朝礼時間を考慮した実績時間範囲
        result_start = hour_start
        if hour_index == 0:
            result_start = hour_start + timedelta(minutes=morning_meeting_duration)
        
        for part_id, part_data in hour_data['parts'].items():
            try:
                from .models import Part
                part = Part.objects.get(id=part_id)
                part_results = results.filter(
                    timestamp__gte=result_start,
                    timestamp__lt=hour_end,
                    judgment='OK',
                    part=part.name
                ).count()
            except Part.DoesNotExist:
                part_results = 0
            
            part_data['actual'] = part_results
            hour_data['total_actual'] += part_results
        
        # 計画がない場合でも実績があれば表示
        existing_part_ids = set(hour_data['parts'].keys())
        actual_part_names = results.filter(
            timestamp__gte=result_start,
            timestamp__lt=hour_end,
            judgment='OK'
        ).values_list('part', flat=True).distinct()
        
        for part_name in actual_part_names:
            if not part_name:
                continue
            try:
                from .models import Part
                part = Part.objects.get(name=part_name)
                part_id = part.id
                if part_id not in existing_part_ids:
                    part_results = results.filter(
                        timestamp__gte=result_start,
                        timestamp__lt=hour_end,
                        judgment='OK',
                        part=part_name
                    ).count()
                    
                    hour_data['parts'][part_id] = {
                        'name': part.name,
                        'color': generate_part_color(part.id, part.name),
                        'planned': 0,
                        'actual': part_results,
                    }
                    hour_data['total_actual'] += part_results
            except Part.DoesNotExist:
                continue
        
        hourly_data.append(hour_data)
    
    return hourly_data


def generate_hourly_data_machine_based(line_id, date, plans, active_machines, results):
    """設備フラグベースの時間別データを生成"""
    # ── 1. 稼働カレンダー取得 ──
    try:
        wc = WorkCalendar.objects.get(line_id=line_id)
        work_start = wc.work_start_time
        morning_meeting_duration = wc.morning_meeting_duration
    except WorkCalendar.DoesNotExist:
        work_start = time(8, 30)
        morning_meeting_duration = 15

    hourly_data = []

    # ── 2. 0時から23時まで１時間刻み ──
    for hour_index in range(24):
        # ナイーブな開始／終了時刻を作成
        naive_start = datetime.combine(date, work_start) + timedelta(hours=hour_index)
        naive_end   = naive_start + timedelta(hours=1)

        # タイムゾーン付きに変換
        aware_start = timezone.make_aware(naive_start)
        aware_end   = timezone.make_aware(naive_end)

        # 朝礼時間を考慮した表示ラベルと実績開始時刻
        display_time = naive_start.strftime('%H:%M')
        if hour_index == 0:
            # 朝礼後開始
            naive_effective = naive_start + timedelta(minutes=morning_meeting_duration)
            display_time = f"{display_time}({naive_effective.strftime('%H:%M')}~)"
            result_start = timezone.make_aware(naive_effective)
        else:
            result_start = aware_start

        # 初期データ構造
        hour_record = {
            'hour':          display_time,
            'total_planned': 0,
            'total_actual':  0,
            'parts':         {},  # { part_id: {name, color, planned, actual}, ... }
        }

        # ── 3. 計画数量を取得 ──
        phps = PlannedHourlyProduction.objects.filter(
            line_id=line_id,
            date=date,
            hour=hour_index
        )
        for php in phps:
            pid = php.part_id
            if pid not in hour_record['parts']:
                hour_record['parts'][pid] = {
                    'name':    php.part.name,
                    'color':   generate_part_color(php.part.id, php.part.name),
                    'planned': 0,
                    'actual':  0,
                }
            hour_record['parts'][pid]['planned']   += php.planned_quantity
            hour_record['total_planned']           += php.planned_quantity

        # ── 4. 実績数量を取得 ──
        # results は既に「line／日付／OK」でフィルタ済みの QuerySet
        # timestamp は文字列形式（YYYYMMDDhhmmss）なので文字列比較を使用
        result_start_str = result_start.strftime('%Y%m%d%H%M%S')
        aware_end_str = aware_end.strftime('%Y%m%d%H%M%S')
        
        hour_qs = results.filter(
            timestamp__gte=result_start_str,
            timestamp__lt=aware_end_str
        )
        
        # レコード数をカウント（ダッシュボードの実績数と一致させる）
        from django.db.models import Count
        part_counts = hour_qs.values('part').annotate(record_count=Count('serial_number'))
        for pc in part_counts:
            # partフィールドから機種名を直接取得
            pname = pc['part']
            qty = pc['record_count'] or 0
            
            # Part オブジェクトを経由して ID と色を取得
            try:
                part_obj = Part.objects.get(name=pname)
            except Part.DoesNotExist:
                continue
            pid = part_obj.id

            # 集計フィールドがなければ初期化
            if pid not in hour_record['parts']:
                hour_record['parts'][pid] = {
                    'name':    part_obj.name,
                    'color':   generate_part_color(part_obj.id, part_obj.name),
                    'planned': 0,
                    'actual':  0,
                }

            # 実績を加算
            hour_record['parts'][pid]['actual']   += qty
            hour_record['total_actual']           += qty

        hourly_data.append(hour_record)

    return hourly_data


def calculate_hourly_planned(hour_start, plans, break_times, morning_meeting):
    """1時間あたりの計画数を計算（要件8: Automatic Hourly Goal Calculation対応）"""
    if not plans:
        return 0
    
    # この時間に該当する計画を取得
    hour_end = hour_start + timedelta(hours=1)
    relevant_plans = []
    
    for plan in plans:
        plan_start = datetime.combine(hour_start.date(), plan.start_time)
        plan_end = datetime.combine(hour_start.date(), plan.end_time)
        
        # 計画時間と1時間の重複をチェック
        overlap_start = max(hour_start, plan_start)
        overlap_end = min(hour_end, plan_end)
        
        if overlap_start < overlap_end:
            # 重複時間（分）
            overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
            
            # 計画の総時間（分）
            plan_duration = (plan_end - plan_start).total_seconds() / 60
            
            # 休憩時間とダウンタイムを除外
            working_minutes = plan_duration - get_break_minutes_in_period(
                plan_start, plan_end, break_times, morning_meeting
            )
            
            if working_minutes > 0:
                # この時間での計画数 = 計画数量 × (重複時間 / 稼働時間)
                hourly_planned = plan.planned_quantity * (overlap_minutes / working_minutes)
                relevant_plans.append(hourly_planned)
    
    return int(sum(relevant_plans))


def get_break_minutes_in_period(start_time, end_time, break_times, morning_meeting):
    """指定期間内の休憩時間（分）を計算"""
    total_break_minutes = 0
    
    # 朝礼時間
    if start_time.time() <= time(8, 45):  # 朝礼は8:30-8:45と仮定
        total_break_minutes += morning_meeting
    
    # 休憩時間
    for break_period in break_times:
        break_start = datetime.strptime(break_period['start'], '%H:%M').time()
        break_end = datetime.strptime(break_period['end'], '%H:%M').time()
        
        break_start_dt = datetime.combine(start_time.date(), break_start)
        break_end_dt = datetime.combine(start_time.date(), break_end)
        
        # 休憩時間と計画時間の重複をチェック
        overlap_start = max(start_time, break_start_dt)
        overlap_end = min(end_time, break_end_dt)
        
        if overlap_start < overlap_end:
            overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
            total_break_minutes += overlap_minutes
    
    return total_break_minutes


def get_accessible_lines(user):
    """ユーザーがアクセス可能なラインを取得"""
    from .models import UserLineAccess, Line
    from django.db import models
    
    # 管理者（スーパーユーザー）の場合は全てのラインにアクセス可能
    if user.is_superuser:
        # 管理者用に疑似的なUserLineAccessオブジェクトを作成
        class MockUserLineAccess:
            def __init__(self, line):
                self.line = line
                self.line_id = line.id
        
        lines = Line.objects.filter(is_active=True)
        return [MockUserLineAccess(line) for line in lines]
    
    return UserLineAccess.objects.filter(user=user).select_related('line')


def has_line_access(user):
    """ユーザーがライン アクセス権限を持っているかチェック"""
    from .models import UserLineAccess
    
    # 管理者（スーパーユーザー）の場合は常にアクセス可能
    if user.is_superuser:
        return True
    
    # 一般ユーザーの場合はUserLineAccessレコードの存在をチェック
    return UserLineAccess.objects.filter(user=user).exists()


def get_user_line_access(user):
    """ユーザーのライン アクセス権限を取得"""
    from .models import UserLineAccess, Line
    
    # 管理者（スーパーユーザー）の場合は全てのアクティブなラインを返す
    if user.is_superuser:
        return Line.objects.filter(is_active=True)
    
    # 一般ユーザーの場合はUserLineAccessから取得
    return Line.objects.filter(
        userlineaccess__user=user,
        is_active=True
    ).distinct()


def update_user_line_access(user, line_ids):
    """ユーザーのライン アクセス権限を更新"""
    from .models import UserLineAccess, Line
    from django.db import transaction
    
    # 管理者の場合は更新しない（常に全アクセス権限を持つため）
    if user.is_superuser:
        return True
    
    try:
        with transaction.atomic():
            # 既存のアクセス権限を削除
            UserLineAccess.objects.filter(user=user).delete()
            
            # 新しいアクセス権限を作成
            if line_ids:
                # 有効なラインIDのみを処理
                valid_lines = Line.objects.filter(id__in=line_ids, is_active=True)
                access_objects = [
                    UserLineAccess(user=user, line=line)
                    for line in valid_lines
                ]
                UserLineAccess.objects.bulk_create(access_objects)
            
            return True
    except Exception as e:
        logger.error(f"ライン アクセス権限の更新に失敗: {e}")
        return False


def has_line_access(user):
    """ユーザーがライン アクセス権限を持っているかチェック"""
    from .models import UserLineAccess
    
    # 管理者（スーパーユーザー）は常にアクセス権限を持つ
    if user.is_superuser:
        return True
    
    # 一般ユーザーはUserLineAccessレコードの存在をチェック
    return UserLineAccess.objects.filter(user=user).exists()


def get_user_line_access(user):
    """ユーザーのライン アクセス権限を全て取得"""
    from .models import UserLineAccess, Line
    
    # 管理者（スーパーユーザー）の場合は全てのアクティブなラインを返す
    if user.is_superuser:
        return Line.objects.filter(is_active=True)
    
    # 一般ユーザーの場合はUserLineAccessから取得
    return Line.objects.filter(
        userlineaccess__user=user,
        is_active=True
    ).distinct()


def update_user_line_access(user, line_ids):
    """ユーザーのライン アクセス権限を一括更新"""
    from .models import UserLineAccess, Line
    from django.db import transaction
    
    # 管理者の場合は更新しない（常に全アクセス権限を持つため）
    if user.is_superuser:
        return True
    
    try:
        with transaction.atomic():
            # 既存のアクセス権限を削除
            UserLineAccess.objects.filter(user=user).delete()
            
            # 新しいアクセス権限を作成
            if line_ids:
                # 有効なラインIDのみを処理
                valid_lines = Line.objects.filter(id__in=line_ids, is_active=True)
                access_objects = [
                    UserLineAccess(user=user, line=line)
                    for line in valid_lines
                ]
                UserLineAccess.objects.bulk_create(access_objects)
            
            return True
    except Exception as e:
        logger.error(f"ライン アクセス権限の更新に失敗: {e}")
        return False


def is_working_day(date):
    """稼働日かどうかを判定"""
    return WorkingDay.is_working_day(date)


def get_week_dates(date):
    """指定日の週の日付リストを取得（月曜始まり）"""
    monday = date - timedelta(days=date.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def get_month_dates(date):
    """指定日の月の日付リストを取得"""
    first_day = date.replace(day=1)
    if date.month == 12:
        next_month = first_day.replace(year=date.year + 1, month=1)
    else:
        next_month = first_day.replace(month=date.month + 1)
    
    dates = []
    current = first_day
    while current < next_month:
        dates.append(current)
        current += timedelta(days=1)
    
    return dates


def send_dashboard_update(line_id, date):
    """ダッシュボードの更新をWebSocketで送信"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    room_group_name = f'dashboard_{line_id}_{date}'
    
    dashboard_data = get_dashboard_data(line_id, date)
    
    async_to_sync(channel_layer.group_send)(
        room_group_name,
        {
            'type': 'dashboard_update',
            'data': dashboard_data
        }
    )


def schedule_full_reaggregation(line_id: int, target_date) -> bool:
    """
    完全再集計をスケジュールする（フォールバック機能）
    
    Args:
        line_id: ライン ID
        target_date: 対象日
        
    Returns:
        bool: スケジュール成功時 True
    """
    try:
        from .services import AggregationService
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"完全再集計スケジュール: ライン ID={line_id}, 日付={target_date}")
        
        # 即座に再集計を実行（本来はキューシステムを使用すべき）
        service = AggregationService()
        count = service.aggregate_single_date(line_id, target_date)
        
        logger.info(f"完全再集計完了: {count}件のレコードを作成")
        return True
        
    except Exception as e:
        logger.error(f"完全再集計スケジュールエラー: {e}")
        return False


def get_weekly_graph_data(line_id, date):
    """
    週別グラフデータを取得（WeeklyResultAggregationのみ使用）
    
    Args:
        line_id: ライン ID
        date: 基準日
        
    Returns:
        dict: 週別グラフデータ
    """
    import logging
    from .services import WeeklyAnalysisService
    
    logger = logging.getLogger(__name__)
    
    try:
        # WeeklyAnalysisServiceの完全版を使用
        logger.info(f"週別グラフデータ取得: WeeklyAnalysisService完全版を使用 - line_id={line_id}")
        service = WeeklyAnalysisService()
        return service.get_complete_weekly_data(line_id, date)
        
    except Exception as e:
        logger.error(f"週別グラフデータ取得エラー: {e}")
        # エラー時は空のデータ構造を返す
        service = WeeklyAnalysisService()
        return service._get_empty_data_structure()


def _get_fallback_weekly_data(line_id, date):
    """
    フォールバック用の週別データ取得（既存の方法）
    
    Args:
        line_id: ライン ID
        date: 基準日
        
    Returns:
        dict: 週別グラフデータ
    """
    import logging
    from .models import Plan, Result, Part, Line
    from django.db import models
    from django.db.models import Q, Sum
    
    logger = logging.getLogger(__name__)
    logger.warning(f"フォールバック方式で週別データを取得: line_id={line_id}")
    
    try:
        # ラインの存在確認
        line = Line.objects.get(id=line_id)
    except Line.DoesNotExist:
        logger.error(f"ライン ID {line_id} が見つかりません")
        # 空のデータ構造を返す
        return {
            'chart_data': {
                'labels': [],
                'planned': [],
                'actual': [],
                'cumulative_planned': [],
                'cumulative_actual': [],
            },
            'weekly_stats': {
                'total_planned': 0,
                'total_actual': 0,
                'achievement_rate': 0,
                'working_days': 0,
                'total_days': 7,
            },
            'available_parts': Part.objects.none(),
            'part_analysis': [],
        }
    
    week_dates = get_week_dates(date)
    
    # 週間データを取得
    weekly_data = []
    total_planned = 0
    total_actual = 0
    
    for day in week_dates:
        try:
            day_data = get_dashboard_data(line_id, day.strftime('%Y-%m-%d'))
            weekly_data.append({
                'date': day.strftime('%Y-%m-%d'),
                'date_display': day.strftime('%m/%d(%a)'),
                'planned': day_data['total_planned'],
                'actual': day_data['total_actual'],
                'achievement_rate': day_data['achievement_rate'],
            })
            total_planned += day_data['total_planned']
            total_actual += day_data['total_actual']
        except Exception as e:
            logger.error(f"日別データ取得エラー: {day} - {e}")
            # エラー時は0データを追加
            weekly_data.append({
                'date': day.strftime('%Y-%m-%d'),
                'date_display': day.strftime('%m/%d(%a)'),
                'planned': 0,
                'actual': 0,
                'achievement_rate': 0,
            })
    
    # 累計データ計算
    cumulative_planned = []
    cumulative_actual = []
    planned_sum = 0
    actual_sum = 0
    
    for d in weekly_data:
        planned_sum += d['planned']
        actual_sum += d['actual']
        cumulative_planned.append(planned_sum)
        cumulative_actual.append(actual_sum)
    
    # チャートデータ生成
    chart_data = {
        'labels': [d['date_display'] for d in weekly_data],
        'planned': [d['planned'] for d in weekly_data],
        'actual': [d['actual'] for d in weekly_data],
        'cumulative_planned': cumulative_planned,
        'cumulative_actual': cumulative_actual,
    }
    
    # 週間統計
    achievement_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
    working_days = sum(1 for d in weekly_data if d['planned'] > 0 or d['actual'] > 0)
    
    weekly_stats = {
        'total_planned': total_planned,
        'total_actual': total_actual,
        'achievement_rate': achievement_rate,
        'working_days': working_days,
        'total_days': 7,
        'planned_trend': 'neutral',
        'actual_trend': 'neutral',
        'achievement_trend': 'neutral',
        'planned_change': 0,
        'actual_change': 0,
        'achievement_change': 0,
    }
    
    # 利用可能機種を取得
    try:
        line = Line.objects.get(id=line_id)
        
        # 計画から機種を取得
        planned_parts = set(Plan.objects.filter(
            line_id=line_id,
            date__in=week_dates
        ).values_list('part__name', flat=True))
        
        # 集計データから機種を取得（より安全）
        from .models import WeeklyResultAggregation
        aggregated_parts = set(WeeklyResultAggregation.objects.filter(
            line=line.name,
            date__in=week_dates
        ).values_list('part', flat=True))
        
        # 両方から機種名を統合
        all_part_names = planned_parts | aggregated_parts
        available_parts = Part.objects.filter(name__in=all_part_names).distinct()
        
    except Line.DoesNotExist:
        available_parts = Part.objects.none()
    
    # 機種別分析
    part_analysis = []
    for part in available_parts:
        # 計画数を集計
        part_planned = (
            Plan.objects.filter(
                line_id=line_id,
                date__in=week_dates,
                part=part
            ).aggregate(total=Sum('planned_quantity'))['total'] or 0
        )
        
        # 実績数を集計（WeeklyResultAggregationから安全に取得）
        part_actual = WeeklyResultAggregation.objects.filter(
            line=line.name,
            part=part.name,
            date__in=week_dates,
            judgment='OK'
        ).aggregate(total=Sum('total_quantity'))['total'] or 0
        
        part_achievement_rate = (part_actual / part_planned * 100) if part_planned > 0 else 0
        
        part_analysis.append({
            'name': part.name,
            'planned': part_planned,
            'actual': part_actual,
            'achievement_rate': part_achievement_rate,
        })
    
    return {
        'chart_data': chart_data,
        'weekly_stats': weekly_stats,
        'available_parts': available_parts,
        'part_analysis': part_analysis,
    }


def _get_monthly_data_from_aggregation(line_id, date):
    """
    WeeklyResultAggregationから月別データを効率的に取得
    
    Args:
        line_id (int): ライン ID
        date (date): 基準日（月の任意の日）
        
    Returns:
        dict: {
            'monthly_data': List[Dict],      # 日別データ
            'monthly_stats': Dict,           # 月別統計
            'chart_data': Dict,              # グラフ用データ
            'calendar_data': List[Dict],     # カレンダー用データ
            'available_parts': QuerySet,     # 利用可能機種
            'part_analysis': Dict            # 機種別分析
        }
    """
    import logging
    from .models import WeeklyResultAggregation, Plan, Part, Line
    from django.db.models import Sum, Q
    from collections import defaultdict
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    logger.info(f"月別データ取得開始: line_id={line_id}, date={date}")
    
    try:
        # ライン情報取得
        line = Line.objects.get(id=line_id)
        line_name = line.name
        
        # 月の日付リスト生成
        month_dates = get_month_dates(date)
        
        # 一括クエリで実績データ取得（最適化版）
        aggregations = WeeklyResultAggregation.objects.filter(
            line=line_name,
            date__in=month_dates
        ).values('date', 'part', 'judgment').annotate(
            total=Sum('total_quantity')
        ).order_by('date', 'part', 'judgment')
        
        # 計画データを一括取得（最適化版：select_related使用）
        plans = Plan.objects.select_related('part').filter(
            line_id=line_id,
            date__in=month_dates
        ).values('date', 'part__name').annotate(
            planned_total=Sum('planned_quantity')
        ).order_by('date', 'part__name')
        
        # 日別データ構築
        daily_data = {}
        for day in month_dates:
            daily_data[day] = {
                'date': day.strftime('%Y-%m-%d'),
                'date_display': day.strftime('%m/%d'),
                'day': day.day,
                'planned': 0,
                'actual': 0,
                'achievement_rate': 0,
            }
        
        # 計画データをマージ
        for plan_data in plans:
            day = plan_data['date']
            if day in daily_data:
                daily_data[day]['planned'] += plan_data['planned_total'] or 0
        
        # 実績データをマージ（OK判定のみ）
        for agg_data in aggregations:
            day = agg_data['date']
            if day in daily_data and agg_data['judgment'] == 'OK':
                daily_data[day]['actual'] += agg_data['total'] or 0
        
        # 達成率計算
        for day_data in daily_data.values():
            if day_data['planned'] > 0:
                day_data['achievement_rate'] = (day_data['actual'] / day_data['planned']) * 100
            else:
                day_data['achievement_rate'] = 0
        
        # 月別データリスト作成
        monthly_data = list(daily_data.values())
        
        # 月別統計計算
        total_planned = sum(d['planned'] for d in monthly_data)
        total_actual = sum(d['actual'] for d in monthly_data)
        achievement_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
        working_days = sum(1 for d in monthly_data if d['planned'] > 0 or d['actual'] > 0)
        
        monthly_stats = {
            'total_planned': total_planned,
            'total_actual': total_actual,
            'achievement_rate': achievement_rate,
            'working_days': working_days,
            'total_days': len(month_dates),
            'planned_trend': 'neutral',
            'actual_trend': 'neutral',
            'achievement_trend': 'neutral',
            'planned_change': 0,
            'actual_change': 0,
            'achievement_change': 0,
        }
        
        logger.info(f"月別データ取得完了: planned={total_planned}, actual={total_actual}, days={len(month_dates)}")
        
        return {
            'monthly_data': monthly_data,
            'monthly_stats': monthly_stats,
            'line_name': line_name,
            'month_dates': month_dates
        }
        
    except Exception as e:
        logger.error(f"月別データ取得エラー: {e}")
        raise


def _calculate_monthly_part_analysis(line_name, month_dates):
    """
    月別機種分析データを計算
    
    Args:
        line_name (str): ライン名
        month_dates (List[date]): 月の日付リスト
        
    Returns:
        Dict: 機種別の計画・実績・達成率データ
    """
    import logging
    from .models import WeeklyResultAggregation, Plan, Part
    from django.db.models import Sum, Q
    from django.db import models
    
    logger = logging.getLogger(__name__)
    logger.info(f"機種別分析計算開始: line={line_name}, days={len(month_dates)}")
    
    try:
        # 利用可能機種を集計データから取得
        available_part_names = list(WeeklyResultAggregation.objects.filter(
            line=line_name,
            date__in=month_dates
        ).values_list('part', flat=True).distinct())
        
        # Partモデルから機種情報を取得
        available_parts = Part.objects.filter(name__in=available_part_names) if available_part_names else Part.objects.none()
        
        # 機種別分析データ構築
        part_analysis = []
        
        for part in available_parts:
            # 計画数量の集計（最適化版：select_related使用）
            part_planned = Plan.objects.select_related('line').filter(
                line__name=line_name,
                date__in=month_dates,
                part=part
            ).aggregate(total=Sum('planned_quantity'))['total'] or 0
            
            # 実績数量の集計（WeeklyResultAggregationから）
            part_actual = WeeklyResultAggregation.objects.filter(
                line=line_name,
                part=part.name,
                date__in=month_dates,
                judgment='OK'
            ).aggregate(total=Sum('total_quantity'))['total'] or 0
            
            # 達成率計算
            part_achievement_rate = (part_actual / part_planned * 100) if part_planned > 0 else 0
            
            # 稼働日数計算（最適化版：select_related使用）
            working_days_count = Plan.objects.select_related('line').filter(
                line__name=line_name,
                date__in=month_dates,
                part=part,
                planned_quantity__gt=0
            ).values('date').distinct().count()
            
            # 平均PPH計算
            average_pph = part_actual / working_days_count if working_days_count > 0 else 0
            
            # 色生成
            part_color = generate_part_color(part.id, part.name)
            
            part_analysis.append({
                'name': part.name,
                'planned': part_planned,
                'actual': part_actual,
                'achievement_rate': part_achievement_rate,
                'working_days': working_days_count,
                'average_pph': average_pph,
                'color': part_color,
            })
        
        logger.info(f"機種別分析計算完了: {len(part_analysis)}機種")
        
        return {
            'available_parts': available_parts,
            'part_analysis': part_analysis
        }
        
    except Exception as e:
        logger.error(f"機種別分析計算エラー: {e}")
        raise


def get_monthly_graph_data(line_id, date):
    """
    月別グラフデータを取得（WeeklyResultAggregation使用版）
    
    新しい実装では、WeeklyResultAggregationテーブルからデータを効率的に取得し、
    従来方式と比較してクエリ実行回数を大幅に削減しています。
    
    Args:
        line_id (int): ライン ID
        date (date): 基準日（月の任意の日）
        
    Returns:
        dict: 月別グラフ表示用の全データ
            - chart_data: グラフ描画用データ
            - monthly_stats: 月別統計情報
            - calendar_data: カレンダー表示用データ
            - weekly_summary: 週別サマリー
            - available_parts: 利用可能機種QuerySet
            - part_analysis: 機種別分析データ
    
    Raises:
        Line.DoesNotExist: 指定されたラインが存在しない場合
        Exception: その他のエラー（フォールバックが実行される）
    """
    import logging
    from collections import defaultdict
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    logger.info(f"月別グラフデータ取得開始: line_id={line_id}, date={date}")
    
    try:
        # WeeklyAnalysisServiceの完全版を使用
        from .services import WeeklyAnalysisService
        service = WeeklyAnalysisService()
        complete_data = service.get_complete_monthly_data(line_id, date.year, date.month)
        
        monthly_data = complete_data['daily_data']
        monthly_stats = complete_data['monthly_stats']
        available_parts = complete_data['available_parts']
        part_analysis = []  # 簡略化
        
        # 累計データ計算
        cumulative_planned = []
        cumulative_actual = []
        planned_sum = 0
        actual_sum = 0
        
        for d in monthly_data:
            planned_sum += d['planned']
            actual_sum += d['actual']
            cumulative_planned.append(planned_sum)
            cumulative_actual.append(actual_sum)
        
        # チャートデータ生成
        chart_data = complete_data['chart_data']
        chart_data.update({
            'cumulative_planned': cumulative_planned,
            'cumulative_actual': cumulative_actual,
        })
        
        # カレンダーデータ（ヒートマップ用）
        calendar_data = []
        for d in monthly_data:
            if d['planned'] > 0:
                achievement = d['achievement_rate']
            else:
                achievement = None
            calendar_data.append(achievement)
        
        # 週別サマリー生成
        weekly_summary = []
        weeks_data = defaultdict(list)
        
        for day_data in monthly_data:
            day_obj = datetime.strptime(day_data['date'], '%Y-%m-%d').date()
            year, week, weekday = day_obj.isocalendar()
            week_key = f"{year}-W{week:02d}"
            weeks_data[week_key].append(day_data)
        
        week_number = 1
        for week_key in sorted(weeks_data.keys()):
            week_days = weeks_data[week_key]
            
            # その週の開始・終了日を計算
            first_day = datetime.strptime(week_days[0]['date'], '%Y-%m-%d').date()
            last_day = datetime.strptime(week_days[-1]['date'], '%Y-%m-%d').date()
            
            # 週の統計計算
            week_planned = sum(d['planned'] for d in week_days)
            week_actual = sum(d['actual'] for d in week_days)
            week_achievement = (week_actual / week_planned * 100) if week_planned > 0 else 0
            working_days_count = sum(1 for d in week_days if d['planned'] > 0 or d['actual'] > 0)
            
            # 平均PPH計算
            average_pph = week_actual / working_days_count if working_days_count > 0 else 0
            
            # 機種数計算（利用可能機種から）
            part_count = len(available_parts)
            
            weekly_summary.append({
                'week_number': week_number,
                'start_date': first_day,
                'end_date': last_day,
                'working_days': working_days_count,
                'planned_quantity': week_planned,
                'actual_quantity': week_actual,
                'achievement_rate': week_achievement,
                'average_pph': average_pph,
                'part_count': part_count,
            })
            week_number += 1
        
        logger.info(f"月別グラフデータ取得完了: weeks={len(weekly_summary)}, parts={len(part_analysis)}")
        
        return {
            'chart_data': chart_data,
            'monthly_stats': monthly_stats,
            'calendar_data': calendar_data,
            'weekly_summary': weekly_summary,
            'available_parts': available_parts,
            'part_analysis': part_analysis,
        }
        
    except Exception as e:
        logger.error(f"月別グラフデータ取得エラー: {e}")
        # フォールバック: 従来の方式を使用
        logger.warning("フォールバック: 従来の方式で月別データを取得します")
        return _get_monthly_graph_data_legacy(line_id, date)


def _get_monthly_graph_data_legacy(line_id, date):
    """
    月別グラフデータを取得（従来方式・フォールバック用）
    """
    from .models import Plan, Result, Part, Machine
    from django.db import models
    from django.db.models import Q
    from collections import defaultdict
    
    month_dates = get_month_dates(date)
    
    # 月間データを取得
    monthly_data = []
    total_planned = 0
    total_actual = 0
    
    for day in month_dates:
        day_data = get_dashboard_data(line_id, day.strftime('%Y-%m-%d'))
        monthly_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'date_display': day.strftime('%m/%d'),
            'day': day.day,
            'planned': day_data['total_planned'],
            'actual': day_data['total_actual'],
            'achievement_rate': day_data['achievement_rate'],
        })
        total_planned += day_data['total_planned']
        total_actual += day_data['total_actual']
    
    # 累計データ計算
    cumulative_planned = []
    cumulative_actual = []
    planned_sum = 0
    actual_sum = 0
    
    for d in monthly_data:
        planned_sum += d['planned']
        actual_sum += d['actual']
        cumulative_planned.append(planned_sum)
        cumulative_actual.append(actual_sum)
    
    # チャートデータ生成
    chart_data = {
        'labels': [d['date_display'] for d in monthly_data],
        'planned': [d['planned'] for d in monthly_data],
        'actual': [d['actual'] for d in monthly_data],
        'cumulative_planned': cumulative_planned,
        'cumulative_actual': cumulative_actual,
    }
    
    # 月間統計
    achievement_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
    working_days = sum(1 for d in monthly_data if d['planned'] > 0 or d['actual'] > 0)
    
    monthly_stats = {
        'total_planned': total_planned,
        'total_actual': total_actual,
        'achievement_rate': achievement_rate,
        'working_days': working_days,
        'total_days': len(month_dates),
        'planned_trend': 'neutral',
        'actual_trend': 'neutral',
        'achievement_trend': 'neutral',
        'planned_change': 0,
        'actual_change': 0,
        'achievement_change': 0,
    }
    
    # カレンダーデータ（ヒートマップ用）
    calendar_data = []
    for d in monthly_data:
        if d['planned'] > 0:
            achievement = d['achievement_rate']
        else:
            achievement = None
        
        calendar_data.append(achievement)
    
    # 週別サマリー生成
    weekly_summary = []
    current_date = month_dates[0]
    
    # 月の第1週から最終週まで処理
    weeks_data = defaultdict(list)
    for day_data in monthly_data:
        day_obj = datetime.strptime(day_data['date'], '%Y-%m-%d').date()
        # ISO週番号を取得
        year, week, weekday = day_obj.isocalendar()
        week_key = f"{year}-W{week:02d}"
        weeks_data[week_key].append(day_data)
    
    week_number = 1
    for week_key in sorted(weeks_data.keys()):
        week_days = weeks_data[week_key]
        
        # その週の開始・終了日を計算
        first_day = datetime.strptime(week_days[0]['date'], '%Y-%m-%d').date()
        last_day = datetime.strptime(week_days[-1]['date'], '%Y-%m-%d').date()
        
        # 週の統計計算
        week_planned = sum(d['planned'] for d in week_days)
        week_actual = sum(d['actual'] for d in week_days)
        week_achievement = (week_actual / week_planned * 100) if week_planned > 0 else 0
        working_days_count = sum(1 for d in week_days if d['planned'] > 0 or d['actual'] > 0)
        
        # 平均PPH計算（仮）
        average_pph = week_actual / working_days_count if working_days_count > 0 else 0
        
        # 機種数計算
        part_count = Part.objects.filter(
            plan__line_id=line_id,
            plan__date__in=[datetime.strptime(d['date'], '%Y-%m-%d').date() for d in week_days]
        ).distinct().count()
        
        weekly_summary.append({
            'week_number': week_number,
            'start_date': first_day,
            'end_date': last_day,
            'working_days': working_days_count,
            'planned_quantity': week_planned,
            'actual_quantity': week_actual,
            'achievement_rate': week_achievement,
            'average_pph': average_pph,
            'part_count': part_count,
        })
        week_number += 1
    
    # 利用可能機種を取得
    available_parts = Part.objects.filter(
        plan__line_id=line_id,
        plan__date__in=month_dates
    ).distinct()
    
    # 機種別分析
    part_analysis = []
    for part in available_parts:
        part_planned = (
            Plan.objects.filter(line_id=line_id, date__in=month_dates, part=part)
            .aggregate(total=models.Sum('planned_quantity'))['total'] or 0
        )
        
        # 稼働中設備での実績を集計
        active_machines = Machine.objects.filter(
            line_id=line_id,
            is_active=True,
            is_production_active=True
        )
        
        part_actual = (
            Result.objects.filter(
                Q(plan__machine__in=active_machines) | Q(machine__in=active_machines),
                Q(plan__part=part) | Q(part=part),
                timestamp__date__in=month_dates,
                judgment='OK'
            ).count()
        )
        
        part_achievement_rate = (part_actual / part_planned * 100) if part_planned > 0 else 0
        
        # 稼働日数計算
        working_days_count = Plan.objects.filter(
            line_id=line_id,
            date__in=month_dates,
            part=part,
            planned_quantity__gt=0
        ).values('date').distinct().count()
        
        # 平均PPH計算
        average_pph = part_actual / working_days_count if working_days_count > 0 else 0
        
        part_analysis.append({
            'name': part.name,
            'planned': part_planned,
            'actual': part_actual,
            'achievement_rate': part_achievement_rate,
            'working_days': working_days_count,
            'average_pph': average_pph,
        })
    
    return {
        'chart_data': chart_data,
        'monthly_stats': monthly_stats,
        'calendar_data': calendar_data,
        'weekly_summary': weekly_summary,
        'available_parts': available_parts,
        'part_analysis': part_analysis,
    }


def get_visible_dashboard_cards():
    """表示設定されたダッシュボードカードを取得"""
    from .models import DashboardCardSetting
    from django.core.cache import cache
    
    cache_key = 'visible_dashboard_cards'
    cached_cards = cache.get(cache_key)
    
    if cached_cards is not None:
        return cached_cards
    
    cards = list(DashboardCardSetting.objects.filter(is_visible=True).order_by('order'))
    cache.set(cache_key, cards, 300)  # 5分キャッシュ
    
    return cards


def is_valid_card_type(card_type):
    """カードタイプが有効かどうかを検証"""
    from .dashboard_cards import DASHBOARD_CARDS
    return card_type in DASHBOARD_CARDS


def get_dashboard_context(line_id, date_str):
    """ダッシュボードコンテキストデータを取得（テスト用）"""
    return get_dashboard_data(line_id, date_str)


def calculate_planned_pph_for_date(line_id, date):
    """指定日の計画PPHを計算（ScheduledPPH.mdの仕様に従い）"""
    
    logger.info(f"計画PPH計算開始: {date}")

    # 1. 前回結果のクリア
    PlannedHourlyProduction.objects.filter(line_id=line_id, date=date).delete()
    logger.info("前回の計画PPH結果をクリアしました")

    # 2. 稼働カレンダー取得
    try:
        wc = WorkCalendar.objects.get(line_id=line_id)
        work_start = wc.work_start_time
        morning_meeting = wc.morning_meeting_duration
        break_times = wc.break_times or wc.get_default_break_times()
    except WorkCalendar.DoesNotExist:
        work_start = time(8, 30)
        morning_meeting = 15
        break_times = [
            {"start": "10:45", "end": "11:00"},
            {"start": "12:00", "end": "12:45"},
            {"start": "15:00", "end": "15:15"},
            {"start": "17:00", "end": "17:15"},
        ]
    logger.info(f"作業開始時間: {work_start}, 朝礼: {morning_meeting}分")

    # 3. 休憩時間を日時にマッピング
    all_breaks = []
    next_day = date + timedelta(days=1)
    for bp in break_times:
        start = datetime.combine(date, datetime.strptime(bp['start'], '%H:%M').time())
        end = datetime.combine(date, datetime.strptime(bp['end'], '%H:%M').time())
        all_breaks.append({'start': start, 'end': end})
        # 翌日早朝の休憩も含める
        if datetime.strptime(bp['start'], '%H:%M').time() < work_start:
            all_breaks.append({
                'start': datetime.combine(next_day, datetime.strptime(bp['start'], '%H:%M').time()),
                'end': datetime.combine(next_day, datetime.strptime(bp['end'], '%H:%M').time())
            })
    logger.info(f"休憩時間: {len(all_breaks)} 件")

    # 4. 段替え時間マップ
    change_map = {(c.from_part_id, c.to_part_id): c.downtime_seconds
                  for c in PartChangeDowntime.objects.filter(line_id=line_id)}
    default_change = 600
    logger.info(f"段替え件数: {len(change_map)}, デフォルト: {default_change}秒")

    # 5. 計画取得
    plans = list(Plan.objects.filter(line_id=line_id, date=date).order_by('sequence'))
    if not plans:
        logger.info("計画データがありません")
        return 0
    logger.info(f"対象計画: {len(plans)} 件")

    # 当日稼働の終端（翌日開始）
    next_day_start = datetime.combine(next_day, work_start)

    # 6. 生産イベント生成（当日内で完結）
    events = []
    current_time = datetime.combine(date, work_start)
    prev_part = None
    stop_day = False

    for plan in plans:
        if stop_day:
            break
        logger.info(f"処理開始: {plan.part.name} 数={plan.planned_quantity}")
        # 段替え
        if prev_part and prev_part != plan.part_id:
            sec = change_map.get((prev_part, plan.part_id), default_change)
            current_time += timedelta(seconds=sec)
            logger.info(f"段替え: +{sec}秒 => {current_time}")

        total_sec = plan.planned_quantity * plan.part.cycle_time
        remaining = total_sec

        while remaining > 0:
            # 稼働可能範囲外チェック
            if current_time >= next_day_start:
                logger.warning(f"稼働可能時間超過: {current_time} >= {next_day_start}。当日計算中断")
                stop_day = True
                break

            logger.info(f"  ループ: 残 {remaining:.1f}s at {current_time}")
            # 次の休憩区間開始
            next_break = next((b for b in all_breaks if b['start'] > current_time), None)
            segment_end = next_break['start'] if next_break else next_day_start
            available = (segment_end - current_time).total_seconds()
            if available <= 0:
                # 休憩中または直後
                if next_break:
                    logger.info(f"    休憩スキップ: {next_break['start']}～{next_break['end']}")
                    current_time = next_break['end']
                    continue
                else:
                    current_time = next_day_start
                    continue

            take = min(remaining, available)
            qty = int(take / plan.part.cycle_time)
            events.append({
                'start_time': current_time,
                'end_time': current_time + timedelta(seconds=take),
                'part_id': plan.part_id,
                'quantity': qty,
            })
            logger.info(f"    イベント: {current_time} +{take:.1f}s => qty={qty}")

            remaining -= take
            current_time += timedelta(seconds=take)

            # 休憩後ジャンプ
            if next_break and current_time >= next_break['start']:
                logger.info(f"    休憩後ジャンプ: {next_break['end']}")
                current_time = next_break['end']

        prev_part = plan.part_id

    logger.info(f"生成イベント数: {len(events)} 件")
    
        # 7. 残りユニット数の管理（計画順序で初期化）
    part_remaining = {}
    for plan in plans:
        part_remaining[plan.part_id] = plan.planned_quantity

    # 8. 各時間帯ごとに計画数量を集計して保存（機種順序厳守）
    saved_count = 0
    
    # 時間帯別の集計結果
    hourly_totals = defaultdict(lambda: defaultdict(lambda: {
        'quantity': 0, 
        'working_seconds': 0, 
        'events': []
    }))
    
    # 機種順序を厳密に守りつつ、時間帯内で効率的に生産
    current_hour = 0  # 現在の時間帯
    used_seconds_in_current_hour = 0  # 現在の時間帯で既に使用した秒数
    
    plan_index = 0  # 現在処理中の計画インデックス
    logger.info("時間帯ごとの配分を開始…")
    while plan_index < len(plans) and current_hour < 48:
        logger.debug(f"  current_hour={current_hour}, plan_index={plan_index}")
        plan = plans[plan_index]
        part_id = plan.part_id
        remaining_qty = part_remaining[part_id]
        
        if remaining_qty <= 0:
            plan_index += 1
            continue
        
        logger.info(f"機種{part_id}の処理: 残りユニット{remaining_qty}個, 時間帯{current_hour}, 使用済み{used_seconds_in_current_hour}秒")
        
        # 現在の時間帯の情報を取得
        hour_start = datetime.combine(date, work_start) + timedelta(hours=current_hour)
        hour_end = hour_start + timedelta(hours=1)
        
        # 最初の時間帯の場合、朝礼時間を考慮
        effective_start = hour_start
        if current_hour == 0:
            effective_start = hour_start + timedelta(minutes=morning_meeting)
        
        # この時間帯での総利用可能時間を計算
        total_available_seconds = (hour_end - effective_start).total_seconds()
        
        # 休憩時間を除外
        break_seconds = 0
        for break_period in all_breaks:
            if break_period['start'] < hour_end and break_period['end'] > effective_start:
                break_overlap_start = max(break_period['start'], effective_start)
                break_overlap_end = min(break_period['end'], hour_end)
                break_seconds += (break_overlap_end - break_overlap_start).total_seconds()
        
        # この時間帯の残り稼働可能時間
        remaining_working_seconds = max(0, total_available_seconds - break_seconds - used_seconds_in_current_hour)
        
        if remaining_working_seconds > 0:
            # この時間帯で生産可能な数量
            cycle_time = plan.part.cycle_time
            potential_quantity = int(remaining_working_seconds / cycle_time)
            actual_quantity = min(potential_quantity, remaining_qty)
            
            if actual_quantity > 0:
                used_time = int(actual_quantity * cycle_time)
                
                # 時間帯別集計に追加
                hourly_totals[current_hour][part_id]['quantity'] += actual_quantity
                hourly_totals[current_hour][part_id]['working_seconds'] += used_time
                hourly_totals[current_hour][part_id]['events'].append({
                    'part_id': part_id,
                    'quantity': actual_quantity,
                    'working_seconds': used_time,
                    'start_time': (effective_start + timedelta(seconds=used_seconds_in_current_hour)).strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': (effective_start + timedelta(seconds=used_seconds_in_current_hour + used_time)).strftime('%Y-%m-%d %H:%M:%S')
                })
                
                remaining_qty -= actual_quantity
                part_remaining[part_id] = remaining_qty
                used_seconds_in_current_hour += used_time
                
                logger.info(f"  時間帯{current_hour}: 機種{part_id} {actual_quantity}個生産, 残り{remaining_qty}個, 使用時間{used_time}秒")
                
                # この機種が完了したら次の機種へ
                if remaining_qty == 0:
                    plan_index += 1
                    continue
            else:
                # この時間帯では生産できない → 次の時間帯へ
                current_hour += 1
                used_seconds_in_current_hour = 0
        else:
            # この時間帯の稼働時間を使い切った → 次の時間帯へ
            current_hour += 1
            used_seconds_in_current_hour = 0
    
    # ScheduledPPH.md仕様：計画数と計画PPHの合計を一致させる
    # 残りユニット数がある場合は、計画順序で追加配分
    for plan in plans:
        part_id = plan.part_id
        remaining_qty = part_remaining[part_id]
        
        if remaining_qty > 0:
            logger.warning(f"機種{part_id}: 残りユニット{remaining_qty}個を順序通り追加配分")
            
            # この機種が既に配分されている最後の時間帯に追加
            last_hour_with_this_part = -1
            for hour_index in range(48):
                if part_id in hourly_totals[hour_index] and hourly_totals[hour_index][part_id]['quantity'] > 0:
                    last_hour_with_this_part = hour_index
            
            if last_hour_with_this_part >= 0:
                # 既存の時間帯に追加
                hourly_totals[last_hour_with_this_part][part_id]['quantity'] += remaining_qty
                hourly_totals[last_hour_with_this_part][part_id]['events'].append({
                    'part_id': part_id,
                    'quantity': remaining_qty,
                    'working_seconds': 0,  # 補正配分のため0秒
                    'start_time': 'adjustment',
                    'end_time': 'adjustment'
                })
            else:
                # この機種が1度も配分されていない場合、最初の時間帯に配分
                if 0 not in hourly_totals:
                    hourly_totals[0] = {}
                
                hourly_totals[0][part_id] = {
                    'quantity': remaining_qty, 
                    'working_seconds': 0, 
                    'events': [{
                        'part_id': part_id,
                        'quantity': remaining_qty,
                        'working_seconds': 0,
                        'start_time': 'adjustment',
                        'end_time': 'adjustment'
                    }]
                }
            
            part_remaining[part_id] = 0
    
    # データベースに保存（ラインごと）
    for hour_index, hour_data in hourly_totals.items():
        for part_id, totals in hour_data.items():
            if totals['quantity'] > 0:
                PlannedHourlyProduction.objects.create(
                    date=date,
                    line_id=line_id,
                    part_id=part_id,
                    hour=hour_index,
                    planned_quantity=totals['quantity'],
                    working_seconds=int(totals['working_seconds']),
                    production_events=totals['events']
                )
                saved_count += 1
    
    # 9. 終了ログの出力 - 計画数と配分数の整合性確認
    total_planned = sum(plan.planned_quantity for plan in plans)
    total_allocated = sum(
        pph['quantity'] 
        for hour_data in hourly_totals.values() 
        for pph in hour_data.values()
    )
    
    logger.info(f"計画PPH計算完了: {saved_count}件保存しました")
    logger.info(f"計画合計: {total_planned}個, 配分合計: {total_allocated}個")
    
    if total_planned != total_allocated:
        logger.error(f"数量不整合: 差異 {total_planned - total_allocated}個")
    else:
        logger.info("数量整合性: OK - ScheduledPPH.md仕様準拠")
    
    return saved_count 