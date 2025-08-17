import random
import string
from datetime import datetime, date, timedelta, time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from production.models import Plan, Result, WorkCalendar, PartChangeDowntime
from django.db import connections, DatabaseError


def generate_unique_serial(existing_serials, length=15):
    """生成されたシリアルが既存セットにないように15桁の数字文字列を返す。"""
    while True:
        serial = ''.join(random.choices(string.digits, k=length))
        if serial not in existing_serials:
            existing_serials.add(serial)
            return serial


class Command(BaseCommand):
    help = (
        '計画データに基づいてサンプル実績データを作成します。'
        'OK=90-110%、NG率5-10%。休憩中はスキップし、日を越えません。'
        '--timeオプションで指定時刻まで実績を制限できます。'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--line',
            type=int,
            help='ラインID（指定しない場合は全ライン）'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='開始日（YYYY-MM-DD形式、指定しない場合は今日）'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='指定日以降何日分実行するか（デフォルト:1日）'
        )
        parser.add_argument(
            '--time',
            type=str,
            help='終了時刻（HH:MM形式、指定した時刻まで実績を生成）'
        )

    def handle(self, *args, **options):
        # 実績テーブルをクリア（Oracleデータベース）
        try:
            # Oracleデータベース接続確認
            oracle_connection = connections['oracle']
            oracle_connection.ensure_connection()
            
            # テーブル存在確認と構造検証
            with oracle_connection.cursor() as cursor:
                try:
                    # テーブル存在確認
                    cursor.execute("SELECT 1 FROM HF1REM01 WHERE ROWNUM = 1")
                    
                    # テーブル構造確認
                    cursor.execute("""
                        SELECT column_name 
                        FROM user_tab_columns 
                        WHERE table_name = 'HF1REM01'
                        ORDER BY column_name
                    """)
                    columns = [row[0] for row in cursor.fetchall()]
                    
                    # 必要な列が存在するかチェック（HF1REM01テーブル用）
                    required_columns = ['MK_DATE', 'M_SERIAL', 'OPEFIN_RESULT', 'STA_NO1', 'STA_NO2', 'STA_NO3', 'PARTSNAME']
                    missing_columns = [col for col in required_columns if col not in columns]
                    
                    if missing_columns:
                        self.stdout.write(
                            self.style.ERROR(
                                f'エラー: テーブル構造が期待と異なります。\n'
                                f'不足している列: {", ".join(missing_columns)}'
                            )
                        )
                        return
                    
                    # 現在のテーブル構造を表示
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'テーブル構造確認完了。列: {", ".join(columns)}'
                        )
                    )
                    
                except DatabaseError as e:
                    if "ORA-00942" in str(e):
                        self.stdout.write(
                            self.style.ERROR(
                                'エラー: Oracleデータベースに実績テーブルが存在しません。\n'
                                '以下のコマンドでマイグレーションを実行してください:\n'
                                'python manage.py migrate production --database=oracle'
                            )
                        )
                        return
                    else:
                        raise
            
            # テーブルが存在する場合のみ削除実行（直接SQL使用）
            with oracle_connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM HF1REM01")
                count_before = cursor.fetchone()[0]
                
                cursor.execute("DELETE FROM HF1REM01")
                oracle_connection.commit()
                
                self.stdout.write(
                    self.style.WARNING(f'既存の実績を全て削除しました（{count_before}件）')
                )
            
        except KeyError:
            self.stdout.write(
                self.style.ERROR(
                    'エラー: Oracleデータベース設定が見つかりません。\n'
                    'settings.pyでoracleデータベース設定を確認してください。'
                )
            )
            return
        except DatabaseError as e:
            if "ORA-00942" in str(e):
                self.stdout.write(
                    self.style.ERROR(
                        'エラー: 実績テーブルにアクセスできません。\n'
                        'テーブルが存在しないか、権限がない可能性があります。\n'
                        'マイグレーションを実行してください: python manage.py migrate production --database=oracle'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Oracleデータベースエラー: {e}')
                )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'予期しないエラー: {e}')
            )
            return

        # 引数から日付範囲を決定
        if options['date']:
            try:
                start_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(
                    '日付の形式が不正です。YYYY-MM-DD で指定してください。'
                ))
                return
        else:
            start_date = timezone.localdate()

        # 終了時刻の解析
        end_time = None
        if options['time']:
            try:
                end_time = datetime.strptime(options['time'], '%H:%M').time()
                self.stdout.write(f'終了時刻設定: {end_time.strftime("%H:%M")}')
            except ValueError:
                self.stderr.write(self.style.ERROR(
                    '時刻の形式が不正です。HH:MM で指定してください。'
                ))
                return

        days = options['days']
        line_filter = {}
        if options['line']:
            line_filter['line_id'] = options['line']

        existing_serials = set()
        total_created = 0

        for delta in range(days):
            plan_date = start_date + timedelta(days=delta)
            plans_qs = Plan.objects.filter(date=plan_date, **line_filter).order_by('sequence')
            if not plans_qs.exists():
                self.stdout.write(f'[{plan_date}] 計画データなし → スキップ')
                continue

            self.stdout.write(f'[{plan_date}] サンプル実績作成開始')
            
            # Oracle接続を各日付処理で再利用
            oracle_connection = connections['oracle']

            # カレンダー取得
            if options['line']:
                wc = WorkCalendar.objects.filter(line_id=options['line']).first()
            else:
                wc = WorkCalendar.objects.filter(
                    line_id__in=plans_qs.values_list('line_id', flat=True)
                ).first()

            if wc:
                work_start = wc.work_start_time
                breaks = wc.break_times or wc.get_default_break_times()
            else:
                work_start = time(8, 30)
                breaks = [
                    {"start": "10:45", "end": "11:00"},
                    {"start": "12:00", "end": "12:45"},
                    {"start": "15:00", "end": "15:15"},
                    {"start": "17:00", "end": "17:15"},
                ]

            # 休憩時間展開
            all_breaks = []
            next_day = plan_date + timedelta(days=1)
            for bp in breaks:
                b_start = datetime.combine(plan_date, datetime.strptime(bp['start'], '%H:%M').time())
                b_end = datetime.combine(plan_date, datetime.strptime(bp['end'], '%H:%M').time())
                all_breaks.append({'start': b_start, 'end': b_end})
                if datetime.strptime(bp['start'], '%H:%M').time() < work_start:
                    all_breaks.append({
                        'start': datetime.combine(next_day, b_start.time()),
                        'end':   datetime.combine(next_day, b_end.time()),
                    })
            next_day_start = datetime.combine(next_day, work_start)

            created = 0
            batch_data = []
            
            # 稼働開始時刻を設定
            current_time = datetime.combine(plan_date, work_start)
            
            # 段取り時間マップを取得
            changeover_map = {}
            if plans_qs.exists():
                line_id = plans_qs.first().line_id
                changeovers = PartChangeDowntime.objects.filter(line_id=line_id)
                for co in changeovers:
                    changeover_map[(co.from_part_id, co.to_part_id)] = co.downtime_seconds
            
            # 段取り時間のデフォルト値（秒）
            default_changeover_time = 600  # 10分
            
            # 計画を順序通りに連続生産
            for plan_index, plan in enumerate(plans_qs):
                # 指定された終了時刻を超えている場合は計画をスキップ
                if end_time and current_time.time() >= end_time:
                    self.stdout.write(f'    計画 {plan_index + 1}: 指定終了時刻({end_time.strftime("%H:%M")})を超過 → スキップ')
                    break
                
                self.stdout.write(f'    計画 {plan_index + 1}: {plan.part.name} ({plan.planned_quantity}個)')
                
                # 段取り時間を追加（最初の計画以外）
                if plan_index > 0:
                    prev_plan = list(plans_qs)[plan_index - 1]
                    changeover_key = (prev_plan.part_id, plan.part_id)
                    changeover_seconds = changeover_map.get(changeover_key, default_changeover_time)
                    
                    # 段取り時間中は休憩チェックをスキップして時間を進める
                    changeover_start = current_time
                    current_time += timedelta(seconds=changeover_seconds)
                    self.stdout.write(f'      段取り時間: {changeover_start.strftime("%H:%M:%S")} → {current_time.strftime("%H:%M:%S")} ({changeover_seconds}秒)')
                    
                    # 段取り後も終了時刻チェック
                    if end_time and current_time.time() >= end_time:
                        self.stdout.write(f'      段取り後に指定終了時刻を超過: {current_time.strftime("%H:%M:%S")} → 計画終了')
                        break
                
                # 実績数量を計算（計画数量の90-110%のOK、5-10%のNG率）
                qty_planned = plan.planned_quantity
                ok_qty = random.randint(int(qty_planned * 0.9), int(qty_planned * 1.1))
                ng_rate = random.uniform(0.05, 0.10)
                total_qty = int(ok_qty / (1 - ng_rate))
                
                # 機種のサイクルタイムを使用（ランダム化）
                base_cycle_time = plan.part.cycle_time if plan.part.cycle_time else 30.0
                
                production_start = current_time
                produced_count = 0
                
                for idx in range(total_qty):
                    # 指定された終了時刻を超えたら終了
                    if end_time and current_time.time() >= end_time:
                        self.stdout.write(f'      指定終了時刻に到達: {current_time.strftime("%H:%M:%S")} → 生産終了')
                        break
                    
                    # 翌日開始時刻を超えたら終了
                    if current_time >= next_day_start:
                        self.stdout.write(f'      翌日開始時刻に到達: {current_time.strftime("%H:%M:%S")} → 生産終了')
                        break
                    
                    # 休憩中なら終了時刻にスキップ
                    br = next((b for b in all_breaks
                               if b['start'] <= current_time < b['end']), None)
                    if br:
                        self.stdout.write(f'      休憩時間: {current_time.strftime("%H:%M:%S")} → {br["end"].strftime("%H:%M:%S")}')
                        current_time = br['end']
                        if current_time >= next_day_start:
                            break
                        # 休憩後も終了時刻チェック
                        if end_time and current_time.time() >= end_time:
                            self.stdout.write(f'      休憩後に指定終了時刻を超過: {current_time.strftime("%H:%M:%S")} → 生産終了')
                            break
                    
                    # サイクルタイムをランダム化（±20%）
                    cycle_sec = random.uniform(base_cycle_time * 0.8, base_cycle_time * 1.2)
                    serial = generate_unique_serial(existing_serials)
                    judgment = 'OK' if idx < ok_qty else 'NG'
                    timestamp = timezone.make_aware(current_time)

                    # HF1REM01テーブル用のデータ形式に変換
                    mk_date = timestamp.strftime('%Y%m%d%H%M%S')
                    opefin_result = '1' if judgment == 'OK' else '2'
                    
                    # バッチデータに追加
                    batch_data.append((
                        mk_date,
                        serial,
                        opefin_result,
                        'SAND',  # STA_NO1
                        plan.line.name,  # STA_NO2
                        plan.machine.name,  # STA_NO3
                        plan.part.name  # partsname
                    ))
                    created += 1
                    produced_count += 1
                    current_time += timedelta(seconds=cycle_sec)
                
                production_end = current_time
                self.stdout.write(f'      生産時間: {production_start.strftime("%H:%M:%S")} → {production_end.strftime("%H:%M:%S")} ({produced_count}個生産)')
            
            # バッチ挿入実行
            if batch_data:
                try:
                    with transaction.atomic(using='oracle'):
                        with oracle_connection.cursor() as cursor:
                            cursor.executemany("""
                                INSERT INTO HF1REM01 
                                (MK_DATE, M_SERIAL, OPEFIN_RESULT, STA_NO1, STA_NO2, STA_NO3, partsname)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, batch_data)
                        
                        self.stdout.write(self.style.SUCCESS(
                            f'  → {plan_date} 完了: {created} 件作成'
                        ))
                        total_created += created
                        
                except DatabaseError as e:
                    if "ORA-00001" in str(e):
                        self.stdout.write(
                            self.style.ERROR(
                                f'エラー: ID重複が発生しました（{plan_date}）\n'
                                f'他のプロセスが同時実行されている可能性があります。'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'バッチ挿入エラー（{plan_date}）: {e}')
                        )
                    continue
            else:
                self.stdout.write(f'  → {plan_date} 完了: 0 件作成（データなし）')

        # 実績データ作成後にダッシュボードキャッシュをクリア
        if total_created > 0:
            try:
                from production.utils import clear_dashboard_cache
                from production.models import Line
                
                # 対象となったラインのキャッシュをクリア
                target_lines = set()
                for delta in range(days):
                    plan_date = start_date + timedelta(days=delta)
                    plans_qs = Plan.objects.filter(date=plan_date, **line_filter)
                    for plan in plans_qs:
                        target_lines.add((plan.line_id, plan_date.strftime('%Y-%m-%d')))
                
                for line_id, date_str in target_lines:
                    clear_dashboard_cache(line_id, date_str)
                    self.stdout.write(f'ダッシュボードキャッシュクリア: ライン{line_id}, 日付{date_str}')
                
                self.stdout.write(self.style.SUCCESS(
                    f'ダッシュボードキャッシュクリア完了: {len(target_lines)}ライン・日付の組み合わせ'
                ))
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'ダッシュボードキャッシュクリアに失敗: {e}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'全日程終了: 合計 {total_created} 件のサンプル実績を作成しました。'
        ))
