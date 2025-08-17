"""
Production API Views

終了予測時刻関連のAPIエンドポイント
"""

import logging
import json
from datetime import datetime, date
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views import View

from .models import Line, ProductionForecastSettings, ProductionForecast
from .services.forecast_service import ForecastCalculationService, OptimizedForecastService
from .utils import get_accessible_lines

logger = logging.getLogger('production.forecast')


class ForecastAPIView(View):
    """
    終了予測取得・計算API
    
    GET: 予測データ取得
    POST: 予測計算実行
    """
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, line_id, date_str):
        """予測データ取得"""
        try:
            # アクセス権限チェック
            if not self._check_line_access(request.user, line_id):
                return JsonResponse(
                    {'error': 'アクセス権限がありません'}, 
                    status=403
                )
            
            line = get_object_or_404(Line, id=line_id)
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 既存の予測データを取得
            try:
                forecast = ProductionForecast.objects.get(
                    line=line, 
                    target_date=target_date
                )
                
                completion_time_str = None
                if forecast.forecast_completion_time:
                    completion_time_str = forecast.forecast_completion_time.strftime('%H:%M')
                
                data = {
                    'success': True,
                    'completion_time': completion_time_str,
                    'is_delayed': forecast.is_delayed,
                    'is_next_day': forecast.is_next_day,
                    'confidence': forecast.confidence_level,
                    'current_production_rate': float(forecast.current_production_rate) if forecast.current_production_rate else 0,
                    'total_planned_quantity': forecast.total_planned_quantity,
                    'total_actual_quantity': forecast.total_actual_quantity,
                    'calculation_timestamp': forecast.calculation_timestamp.isoformat(),
                    'error_message': forecast.error_message
                }
                
                if forecast.error_message:
                    data['message'] = forecast.error_message
                elif not forecast.forecast_completion_time:
                    data['message'] = '実績データなし'
                
                return JsonResponse(data)
                
            except ProductionForecast.DoesNotExist:
                # 予測データが存在しない場合、新規計算
                return self._calculate_forecast(line_id, target_date)
        
        except ValueError:
            return JsonResponse(
                {'error': '無効な日付形式です'}, 
                status=400
            )
        except Exception as e:
            logger.error(f"予測データ取得エラー: {e}", exc_info=True)
            return JsonResponse(
                {'error': '予測データ取得に失敗しました'}, 
                status=500
            )
    
    def post(self, request, line_id, date_str):
        """予測計算実行"""
        try:
            # アクセス権限チェック
            if not self._check_line_access(request.user, line_id):
                return JsonResponse(
                    {'error': 'アクセス権限がありません'}, 
                    status=403
                )
            
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            return self._calculate_forecast(line_id, target_date)
            
        except ValueError:
            return JsonResponse(
                {'error': '無効な日付形式です'}, 
                status=400
            )
        except Exception as e:
            logger.error(f"予測計算エラー: {e}", exc_info=True)
            return JsonResponse(
                {'error': '予測計算に失敗しました'}, 
                status=500
            )
    
    def _calculate_forecast(self, line_id: int, target_date: date) -> JsonResponse:
        """予測計算実行（最適化版）"""
        service = OptimizedForecastService()
        
        # OptimizedForecastServiceは予測時刻文字列を返すため、レスポンス形式を調整
        try:
            forecast_time_str = service.get_forecast_time(line_id, target_date)
            
            # エラーケースの処理
            if forecast_time_str in ['計画なし', '完了済み', '計算エラー']:
                result = {
                    'success': True,
                    'completion_time': None,
                    'message': forecast_time_str,
                    'confidence': 0 if forecast_time_str == '計算エラー' else 100
                }
            else:
                # 正常な時刻が返された場合
                from datetime import datetime
                try:
                    completion_time = datetime.strptime(forecast_time_str, '%H:%M').time()
                    result = {
                        'success': True,
                        'completion_time': completion_time,
                        'confidence': 85,  # 最適化版のデフォルト信頼度
                        'is_delayed': completion_time > datetime.strptime('17:00', '%H:%M').time(),
                        'is_next_day': False  # OptimizedForecastServiceでは当日完了前提
                    }
                except ValueError:
                    result = {
                        'success': False,
                        'error': '時刻解析エラー',
                        'message': '計算エラー'
                    }
        except Exception as e:
            logger.error(f"最適化予測計算エラー: {e}", exc_info=True)
            result = {
                'success': False,
                'error': str(e),
                'message': '計算エラー'
            }
        
        if result['success']:
            # 正常計算結果
            completion_time_str = None
            if result.get('completion_time'):
                completion_time_str = result['completion_time'].strftime('%H:%M')
            
            response_data = {
                'success': True,
                'completion_time': completion_time_str,
                'is_delayed': result.get('is_delayed', False),
                'is_next_day': result.get('is_next_day', False),
                'confidence': result.get('confidence', 0),
                'current_production_rate': result.get('current_rate', 0),
                'total_planned_quantity': result.get('total_planned', 0),
                'total_actual_quantity': result.get('total_actual', 0),
                'calculation_timestamp': timezone.now().isoformat()
            }
            
            if result.get('message'):
                response_data['message'] = result['message']
            
            return JsonResponse(response_data)
        else:
            # エラー結果
            return JsonResponse({
                'success': False,
                'error': result.get('error', '計算エラー'),
                'message': result.get('message', '計算エラー')
            }, status=500)
    
    def _check_line_access(self, user, line_id: int) -> bool:
        """ライン アクセス権限チェック"""
        if user.is_superuser:
            return True
        
        accessible_lines = get_accessible_lines(user)
        return accessible_lines.filter(line_id=line_id).exists()


class ForecastSettingsAPIView(View):
    """
    終了予測設定API
    
    GET: 設定取得
    POST: 設定更新
    """
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, line_id):
        """設定取得"""
        try:
            # アクセス権限チェック
            if not self._check_line_access(request.user, line_id):
                return JsonResponse(
                    {'error': 'アクセス権限がありません'}, 
                    status=403
                )
            
            line = get_object_or_404(Line, id=line_id)
            
            try:
                settings = ProductionForecastSettings.objects.get(line=line)
            except ProductionForecastSettings.DoesNotExist:
                # デフォルト設定を作成
                settings = ProductionForecastSettings.objects.create(line=line)
            
            return JsonResponse({
                'success': True,
                'calculation_interval_minutes': settings.calculation_interval_minutes,
                'is_active': settings.is_active,
                'updated_at': settings.updated_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"設定取得エラー: {e}", exc_info=True)
            return JsonResponse(
                {'error': '設定取得に失敗しました'}, 
                status=500
            )
    
    def post(self, request, line_id):
        """設定更新"""
        try:
            # 管理者権限チェック
            if not request.user.is_superuser:
                return JsonResponse(
                    {'error': '管理者権限が必要です'}, 
                    status=403
                )
            
            line = get_object_or_404(Line, id=line_id)
            
            # リクエストデータ取得
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = request.POST
            
            interval = data.get('calculation_interval_minutes')
            is_active = data.get('is_active')
            
            # バリデーション
            if interval is not None:
                try:
                    interval = int(interval)
                    if not (1 <= interval <= 60):
                        return JsonResponse(
                            {'error': '計算間隔は1-60分の範囲で指定してください'}, 
                            status=400
                        )
                except (ValueError, TypeError):
                    return JsonResponse(
                        {'error': '計算間隔は数値で指定してください'}, 
                        status=400
                    )
            
            # 設定更新
            settings, created = ProductionForecastSettings.objects.get_or_create(
                line=line,
                defaults={'calculation_interval_minutes': 15, 'is_active': True}
            )
            
            if interval is not None:
                settings.calculation_interval_minutes = interval
            if is_active is not None:
                settings.is_active = bool(is_active)
            
            settings.save()
            
            logger.info(f"予測設定更新: {line.name} - {settings.calculation_interval_minutes}分間隔")
            
            return JsonResponse({
                'success': True,
                'calculation_interval_minutes': settings.calculation_interval_minutes,
                'is_active': settings.is_active,
                'updated_at': settings.updated_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"設定更新エラー: {e}", exc_info=True)
            return JsonResponse(
                {'error': '設定更新に失敗しました'}, 
                status=500
            )
    
    def _check_line_access(self, user, line_id: int) -> bool:
        """ライン アクセス権限チェック"""
        if user.is_superuser:
            return True
        
        accessible_lines = get_accessible_lines(user)
        return accessible_lines.filter(line_id=line_id).exists()


# 関数ベースビュー（簡単なJSONレスポンス用）
@csrf_exempt
@login_required
def forecast_json_view(request, line_id, date_str):
    """
    JSON形式で予測データ取得
    (AjaxやWebSocketでの取得用)
    """
    try:
        # アクセス権限チェック
        if not request.user.is_superuser:
            accessible_lines = get_accessible_lines(request.user)
            if not accessible_lines.filter(line_id=line_id).exists():
                return JsonResponse({'error': 'アクセス権限がありません'}, status=403)
        
        # ForecastAPIViewと同じロジック
        api_view = ForecastAPIView()
        api_view.request = request
        
        if request.method == 'GET':
            return api_view.get(request, line_id, date_str)
        elif request.method == 'POST':
            return api_view.post(request, line_id, date_str)
        else:
            return JsonResponse({'error': '無効なメソッドです'}, status=405)
            
    except Exception as e:
        logger.error(f"JSON予測データ取得エラー: {e}", exc_info=True)
        return JsonResponse(
            {'error': '予測データ取得に失敗しました'}, 
            status=500
        )