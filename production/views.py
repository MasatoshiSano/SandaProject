from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
)
from django.views import View
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, date, timedelta
import json
from calendar import monthrange
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string

from .models import (
    Line, Plan, Part, Category, Tag, Result, Machine, UserLineAccess, UserPreference, Feedback
)
from .forms import (
    PlanForm, PartForm, CategoryForm, TagForm, ResultForm, LineSelectForm, ResultFilterForm, FeedbackForm, FeedbackEditForm
)
from .utils import (
    get_dashboard_data, get_accessible_lines, get_week_dates, get_month_dates,
    send_dashboard_update
)


class LineAccessMixin(LoginRequiredMixin):
    """ライン アクセス権限チェック用ミックスイン"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # 管理者（スーパーユーザー）はアクセス権限チェックをスキップ
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        line_id = kwargs.get('line_id')
        if line_id:
            accessible_lines = get_accessible_lines(request.user)
            if not accessible_lines.filter(line_id=line_id).exists():
                return HttpResponseForbidden("このラインへのアクセス権限がありません。")
        
        return super().dispatch(request, *args, **kwargs)


class LineSelectView(LoginRequiredMixin, TemplateView):
    """ライン選択ビュー"""
    template_name = 'production/line_select.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ユーザーの設定を取得
        try:
            user_pref = UserPreference.objects.get(user=self.request.user)
            initial_line = user_pref.last_selected_line
        except UserPreference.DoesNotExist:
            initial_line = None
        
        form = LineSelectForm(user=self.request.user)
        if initial_line:
            form.fields['line'].initial = initial_line
        
        context['form'] = form
        context['accessible_lines'] = get_accessible_lines(self.request.user)
        return context
    
    def post(self, request, *args, **kwargs):
        form = LineSelectForm(request.POST, user=request.user)
        if form.is_valid():
            line = form.cleaned_data['line']
            date = form.cleaned_data['date']
            
            # ユーザー設定を更新
            user_pref, created = UserPreference.objects.get_or_create(user=request.user)
            user_pref.last_selected_line = line
            user_pref.save()
            
            return redirect('production:dashboard', line_id=line.id, date=date.strftime('%Y-%m-%d'))
        
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)


class DashboardView(LineAccessMixin, TemplateView):
    """ダッシュボードビュー"""
    template_name = 'production/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        line_id = kwargs['line_id']
        date_str = kwargs.get('date', timezone.now().date().strftime('%Y-%m-%d'))
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date_obj = timezone.now().date()
            date_str = date_obj.strftime('%Y-%m-%d')
        
        line = get_object_or_404(Line, id=line_id)
        dashboard_data = get_dashboard_data(line_id, date_str)
        
        context.update({
            'line': line,
            'date': date_obj,
            'date_str': date_str,
            'dashboard_data': dashboard_data,
            'prev_date': (date_obj - timedelta(days=1)).strftime('%Y-%m-%d'),
            'next_date': (date_obj + timedelta(days=1)).strftime('%Y-%m-%d'),
        })
        return context


class PlanListView(LineAccessMixin, ListView):
    """計画一覧ビュー"""
    model = Plan
    template_name = 'production/plan_list.html'
    context_object_name = 'plans'
    
    def get_queryset(self):
        line_id = self.kwargs['line_id']
        date_str = self.kwargs['date']
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date_obj = timezone.now().date()
        
        return Plan.objects.filter(
            line_id=line_id, 
            date=date_obj
        ).select_related('part', 'part__category').order_by('sequence')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        line_id = self.kwargs['line_id']
        date_str = self.kwargs['date']
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date_obj = timezone.now().date()
            date_str = date_obj.strftime('%Y-%m-%d')
        
        line = get_object_or_404(Line, id=line_id)
        
        context.update({
            'line': line,
            'date': date_obj,
            'date_str': date_str,
        })
        return context


class PlanCreateView(LineAccessMixin, CreateView):
    """計画作成ビュー"""
    model = Plan
    form_class = PlanForm
    template_name = 'production/plan_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['line_id'] = self.kwargs['line_id']
        return kwargs
    

    
    def get_initial(self):
        initial = super().get_initial()
        line_id = self.kwargs['line_id']
        date_str = self.kwargs['date']
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date_obj = timezone.now().date()
        
        # 次の順番を自動設定
        last_plan = Plan.objects.filter(line_id=line_id, date=date_obj).order_by('-sequence').first()
        next_sequence = (last_plan.sequence + 1) if last_plan else 1
        
        # デフォルトの機械を取得
        default_machine = Machine.objects.filter(line_id=line_id, is_active=True).first()
        
        initial.update({
            'line': line_id,
            'machine': default_machine.id if default_machine else None,
            'date': date_obj,
            'sequence': next_sequence,
            'start_time': '08:00',
            'end_time': '17:00',
        })
        return initial
    
    def get_success_url(self):
        line_id = self.kwargs['line_id']
        date_str = self.kwargs['date']
        messages.success(self.request, '計画を作成しました。')
        return reverse('production:plan_list', kwargs={'line_id': line_id, 'date': date_str})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        line_id = self.kwargs['line_id']
        date_str = self.kwargs['date']
        line = get_object_or_404(Line, id=line_id)
        
        context.update({
            'line': line,
            'date_str': date_str,
            'action': '作成',
        })
        return context


class PlanUpdateView(LineAccessMixin, UpdateView):
    """計画更新ビュー"""
    model = Plan
    form_class = PlanForm
    template_name = 'production/plan_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['line_id'] = self.object.line.id
        return kwargs
    
    def get_success_url(self):
        messages.success(self.request, '計画を更新しました。')
        return reverse('production:plan_list', kwargs={
            'line_id': self.object.line.id,
            'date': self.object.date.strftime('%Y-%m-%d')
        })
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'line': self.object.line,
            'date_str': self.object.date.strftime('%Y-%m-%d'),
            'action': '更新',
        })
        return context


class PlanDeleteView(LineAccessMixin, DeleteView):
    """計画削除ビュー"""
    model = Plan
    template_name = 'production/plan_confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, '計画を削除しました。')
        return reverse('production:plan_list', kwargs={
            'line_id': self.object.line.id,
            'date': self.object.date.strftime('%Y-%m-%d')
        })


class PartCreateView(LoginRequiredMixin, CreateView):
    """機種作成ビュー"""
    model = Part
    form_class = PartForm
    template_name = 'production/part_form.html'
    success_url = reverse_lazy('production:part_list')
    
    def form_valid(self, form):
        messages.success(self.request, '機種を作成しました。')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_str'] = timezone.now().date().strftime('%Y-%m-%d')
        context['available_tags'] = Tag.objects.filter(is_active=True)
        return context


class PartUpdateView(LoginRequiredMixin, UpdateView):
    """機種更新ビュー"""
    model = Part
    form_class = PartForm
    template_name = 'production/part_form.html'
    success_url = reverse_lazy('production:part_list')
    
    def form_valid(self, form):
        messages.success(self.request, '機種を更新しました。')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_str'] = timezone.now().date().strftime('%Y-%m-%d')
        context['available_tags'] = Tag.objects.filter(is_active=True)
        return context


class PartListView(LoginRequiredMixin, ListView):
    """機種一覧ビュー"""
    model = Part
    template_name = 'production/part_list.html'
    context_object_name = 'parts'
    paginate_by = 20
    
    def get_queryset(self):
        return Part.objects.filter(is_active=True).order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_str'] = timezone.now().date().strftime('%Y-%m-%d')
        
        # アクセス可能なラインを取得
        accessible_lines = get_accessible_lines(self.request.user)
        context['accessible_lines'] = accessible_lines
        
        # デフォルトライン（計画作成リンク用）
        if accessible_lines:
            if hasattr(accessible_lines[0], 'line'):
                context['default_line'] = accessible_lines[0].line
            else:
                context['default_line'] = accessible_lines[0]
        
        return context


class CategoryCreateView(LoginRequiredMixin, CreateView):
    """カテゴリ作成ビュー"""
    model = Category
    form_class = CategoryForm
    template_name = 'production/category_form.html'
    
    def form_valid(self, form):
        messages.success(self.request, 'カテゴリを作成しました。')
        return super().form_valid(form)
    
    def get_success_url(self):
        # モーダルから呼ばれた場合は閉じる
        if self.request.GET.get('modal'):
            return reverse('production:part_create')
        return reverse('production:part_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_str'] = timezone.now().date().strftime('%Y-%m-%d')
        return context


class TagCreateView(LoginRequiredMixin, CreateView):
    """タグ作成ビュー"""
    model = Tag
    form_class = TagForm
    template_name = 'production/tag_form.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Ajaxリクエストの場合はJSONレスポンスを返す
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in self.request.headers.get('Accept', ''):
            return JsonResponse({
                'success': True,
                'tag': {
                    'id': self.object.id,
                    'name': self.object.name,
                    'description': self.object.description,
                    'color': self.object.color,
                }
            })
        
        messages.success(self.request, 'タグを作成しました。')
        return response
    
    def form_invalid(self, form):
        # Ajaxリクエストの場合はJSONレスポンスを返す
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in self.request.headers.get('Accept', ''):
            return JsonResponse({
                'success': False,
                'error': form.errors
            })
        
        return super().form_invalid(form)
    
    def get_success_url(self):
        # モーダルから呼ばれた場合は閉じる
        if self.request.GET.get('modal'):
            return reverse('production:part_create')
        return reverse('production:part_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_str'] = timezone.now().date().strftime('%Y-%m-%d')
        return context


class ResultListView(LineAccessMixin, ListView):
    """実績一覧ビュー"""
    model = Result
    template_name = 'production/result_list.html'
    context_object_name = 'results'
    paginate_by = 50
    
    def get_queryset(self):
        line_id = self.kwargs['line_id']
        
        try:
            line = Line.objects.get(id=line_id)
            queryset = Result.objects.filter(line=line.name).order_by('-timestamp')
        except Line.DoesNotExist:
            queryset = Result.objects.none()
        
        # フィルタが適用されていない場合は、最近3日間のデータを表示
        if not any(self.request.GET.values()):
            three_days_ago = timezone.now() - timedelta(days=3)
            return queryset.filter(timestamp__gte=three_days_ago)
        
        # フィルタ適用
        form = ResultFilterForm(self.request.GET, line_id=line_id)
        if form.is_valid():
            if form.cleaned_data['timestamp_start']:
                queryset = queryset.filter(timestamp__gte=form.cleaned_data['timestamp_start'])
            if form.cleaned_data['timestamp_end']:
                queryset = queryset.filter(timestamp__lte=form.cleaned_data['timestamp_end'])
            if form.cleaned_data['plan']:
                queryset = queryset.filter(plan=form.cleaned_data['plan'])
            if form.cleaned_data['part']:
                queryset = queryset.filter(plan__part=form.cleaned_data['part'])
            if form.cleaned_data['category']:
                queryset = queryset.filter(plan__part__category=form.cleaned_data['category'])
            if form.cleaned_data['machine']:
                queryset = queryset.filter(plan__machine=form.cleaned_data['machine'])
            if form.cleaned_data['quantity_min']:
                queryset = queryset.filter(quantity__gte=form.cleaned_data['quantity_min'])
            if form.cleaned_data['quantity_max']:
                queryset = queryset.filter(quantity__lte=form.cleaned_data['quantity_max'])
            if form.cleaned_data['serial_number']:
                queryset = queryset.filter(serial_number__icontains=form.cleaned_data['serial_number'])
            if form.cleaned_data['judgment']:
                queryset = queryset.filter(judgment=form.cleaned_data['judgment'])
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        line_id = self.kwargs['line_id']
        line = get_object_or_404(Line, id=line_id)
        
        # 現在の日付をdate_strとして設定（ナビゲーションメニュー用）
        date_str = timezone.now().date().strftime('%Y-%m-%d')
        
        # 実績にpart_categoryを追加
        results = context['results']
        for result in results:
            try:
                part = Part.objects.get(name=result.part)
                result.part_category = part.category.name
            except Part.DoesNotExist:
                result.part_category = None
        
        context.update({
            'line': line,
            'date_str': date_str,
            'filter_form': ResultFilterForm(self.request.GET, line_id=line_id),
        })
        return context


class ResultCreateView(LoginRequiredMixin, CreateView):
    """実績作成ビュー"""
    model = Result
    form_class = ResultForm
    template_name = 'production/result_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        # URLパラメータからline_idを取得（オプション）
        line_id = self.request.GET.get('line_id')
        if line_id:
            kwargs['line_id'] = line_id
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        initial['timestamp'] = timezone.now()
        # URLパラメータからplan_idを取得してデフォルト値に設定
        plan_id = self.request.GET.get('plan')
        if plan_id:
            try:
                plan = Plan.objects.get(id=plan_id)
                initial['plan'] = plan
            except Plan.DoesNotExist:
                pass
        return initial
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '実績を登録しました。')
        
        # WebSocketでダッシュボード更新を送信
        result = form.instance
        date_str = result.timestamp.date().strftime('%Y-%m-%d')
        send_dashboard_update(result.line.id, date_str)
        
        return response
    
    def get_success_url(self):
        return reverse('production:result_list', kwargs={'line_id': self.object.line.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_str'] = timezone.now().date().strftime('%Y-%m-%d')
        
        # アクセス可能なラインを取得
        accessible_lines = get_accessible_lines(self.request.user)
        context['accessible_lines'] = accessible_lines
        
        # デフォルトライン（戻るボタン用）
        if accessible_lines:
            if hasattr(accessible_lines[0], 'line'):
                context['default_line'] = accessible_lines[0].line
            else:
                context['default_line'] = accessible_lines[0]
        
        return context


class ResultUpdateView(LoginRequiredMixin, UpdateView):
    """実績更新ビュー"""
    model = Result
    form_class = ResultForm
    template_name = 'production/result_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['line_id'] = self.object.line.id
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '実績を更新しました。')
        
        # WebSocketでダッシュボード更新を送信
        result = form.instance
        date_str = result.timestamp.date().strftime('%Y-%m-%d')
        send_dashboard_update(result.line.id, date_str)
        
        return response
    
    def get_success_url(self):
        return reverse('production:result_list', kwargs={'line_id': self.object.line.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_str'] = timezone.now().date().strftime('%Y-%m-%d')
        
        # アクセス可能なラインを取得
        accessible_lines = get_accessible_lines(self.request.user)
        context['accessible_lines'] = accessible_lines
        
        # デフォルトライン（戻るボタン用）
        if accessible_lines:
            if hasattr(accessible_lines[0], 'line'):
                context['default_line'] = accessible_lines[0].line
            else:
                context['default_line'] = accessible_lines[0]
        
        return context


class ResultDeleteView(LoginRequiredMixin, DeleteView):
    """実績削除ビュー"""
    model = Result
    template_name = 'production/result_confirm_delete.html'
    
    def get_success_url(self):
        return reverse('production:result_list', kwargs={'line_id': self.object.line.id})
    
    def delete(self, request, *args, **kwargs):
        result = self.get_object()
        messages.success(request, f'実績を削除しました。')
        
        # WebSocketでダッシュボード更新を送信
        date_str = result.timestamp.date().strftime('%Y-%m-%d')
        send_dashboard_update(result.line.id, date_str)
        
        return super().delete(request, *args, **kwargs)


class WeeklyGraphView(LineAccessMixin, TemplateView):
    """週別グラフビュー"""
    template_name = 'production/weekly_graph.html'
    
    def get_context_data(self, **kwargs):
        from .utils import get_weekly_graph_data, get_week_dates
        import json
        from datetime import datetime, timedelta
        
        context = super().get_context_data(**kwargs)
        line_id = kwargs['line_id']
        
        # 週指定の処理（week=2025-W01形式またはdate=2025-01-01形式）
        week_param = self.request.GET.get('week')
        date_param = self.request.GET.get('date')
        
        if week_param:
            try:
                # ISO週番号からの日付計算
                year = int(week_param.split('-W')[0])
                week = int(week_param.split('-W')[1])
                # その年の1月4日を基準に週を計算（ISO 8601の規定）
                jan4 = datetime(year, 1, 4)
                # 1月4日の曜日を取得（月曜が1、日曜が7）
                jan4_day = jan4.isoweekday()
                # 1月4日から月曜日までさかのぼる
                week1_start = jan4 - timedelta(days=jan4_day - 1)
                # 目的の週の開始日を計算
                target_date = week1_start + timedelta(weeks=week-1)
                date_obj = target_date.date()
            except (ValueError, IndexError):
                date_obj = timezone.now().date()
        elif date_param:
            try:
                date_obj = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                date_obj = timezone.now().date()
        else:
            date_obj = timezone.now().date()
        
        line = get_object_or_404(Line, id=line_id)
        
        # 週の開始日（月曜日）を取得
        week_start = date_obj - timedelta(days=date_obj.weekday())
        week_dates = [week_start + timedelta(days=i) for i in range(7)]
        
        # 週別グラフデータを取得
        graph_data = get_weekly_graph_data(line_id, date_obj)
        
        # JSONシリアライズ
        chart_data_json = json.dumps(graph_data['chart_data'])
        
        # 年と週番号を計算
        year, week_num, _ = date_obj.isocalendar()
        
        context.update({
            'line': line,
            'date': date_obj,
            'date_str': date_obj.strftime('%Y-%m-%d'),
            'current_week': date_obj,
            'week_dates': week_dates,
            'period': 'weekly',
            'chart_data_json': chart_data_json,
            'chart_data': graph_data['chart_data'],
            'weekly_stats': graph_data['weekly_stats'],
            'available_parts': graph_data['available_parts'],
            'part_analysis': graph_data['part_analysis'],
            'year': year,
            'week_num': week_num,
        })
        return context


class MonthlyGraphView(LineAccessMixin, TemplateView):
    """月別グラフビュー"""
    template_name = 'production/monthly_graph.html'
    
    def get_context_data(self, **kwargs):
        from .utils import get_monthly_graph_data
        import json
        from datetime import datetime, timedelta, date
        from calendar import monthrange
        
        context = super().get_context_data(**kwargs)
        line_id = kwargs['line_id']
        
        # 月指定の処理（month=2025-01形式またはdate=2025-01-01形式）
        month_param = self.request.GET.get('month')
        date_param = self.request.GET.get('date')
        
        if month_param:
            try:
                date_obj = datetime.strptime(f'{month_param}-01', '%Y-%m-%d').date()
            except ValueError:
                date_obj = timezone.now().date()
        elif date_param:
            try:
                date_obj = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                date_obj = timezone.now().date()
        else:
            date_obj = timezone.now().date()
        
        line = get_object_or_404(Line, id=line_id)
        
        # 月の最初の日と最後の日を取得
        year = date_obj.year
        month = date_obj.month
        _, last_day = monthrange(year, month)
        first_date = date(year, month, 1)
        last_date = date(year, month, last_day)
        
        # 月の最初の週の日曜日を取得
        first_sunday = first_date - timedelta(days=first_date.weekday() + 1)
        
        # カレンダー用の週データを生成
        calendar_weeks = []
        current_date = first_sunday
        while current_date <= last_date:
            week = []
            for _ in range(7):
                week.append({
                    'date': current_date,
                    'in_month': current_date.month == month
                })
                current_date += timedelta(days=1)
            calendar_weeks.append(week)
        
        # 月別グラフデータを取得
        graph_data = get_monthly_graph_data(line_id, date_obj)
        
        # JSONシリアライズ
        chart_data_json = json.dumps(graph_data['chart_data'])
        calendar_data_json = json.dumps(graph_data['calendar_data'])
        
        context.update({
            'line': line,
            'date': date_obj,
            'date_str': date_obj.strftime('%Y-%m-%d'),
            'current_month': date_obj,
            'period': 'monthly',
            'chart_data_json': chart_data_json,
            'calendar_data_json': calendar_data_json,
            'chart_data': graph_data['chart_data'],
            'monthly_stats': graph_data['monthly_stats'],
            'calendar_data': graph_data['calendar_data'],
            'calendar_weeks': calendar_weeks,
            'weekly_summary': graph_data['weekly_summary'],
            'available_parts': graph_data['available_parts'],
            'part_analysis': graph_data['part_analysis'],
        })
        return context


class DashboardDataAPIView(LineAccessMixin, View):
    """ダッシュボードデータAPI"""
    
    def get(self, request, line_id, date):
        data = get_dashboard_data(line_id, date)
        return JsonResponse(data)


class GraphDataAPIView(LineAccessMixin, View):
    """グラフデータAPI"""
    
    def get(self, request, line_id, period, date):
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            date_obj = timezone.now().date()
        
        if period == 'weekly':
            dates = get_week_dates(date_obj)
        elif period == 'monthly':
            dates = get_month_dates(date_obj)
        else:
            return JsonResponse({'error': 'Invalid period'}, status=400)
        
        # 各日のデータを取得
        data = []
        for d in dates:
            day_data = get_dashboard_data(line_id, d.strftime('%Y-%m-%d'))
            data.append({
                'date': d.strftime('%Y-%m-%d'),
                'total_planned': day_data['total_planned'],
                'total_actual': day_data['total_actual'],
                'parts': day_data['parts'],
            })
        
        return JsonResponse({'data': data})


class PartInfoAPIView(LoginRequiredMixin, View):
    """機種情報API"""
    
    def get(self, request, part_id):
        try:
            part = Part.objects.get(id=part_id)
            data = {
                'id': part.id,
                'name': part.name,
                'part_number': part.part_number,
                'category': part.category.name,
                'target_pph': part.target_pph,
                'cycle_time': part.cycle_time,
                'tags': [tag.name for tag in part.tags.all()],
            }
            return JsonResponse(data)
        except Part.DoesNotExist:
            return JsonResponse({'error': 'Part not found'}, status=404)


class PlanInfoAPIView(LineAccessMixin, View):
    """計画情報API"""
    
    def get(self, request, plan_id):
        try:
            plan = Plan.objects.select_related('part', 'line', 'machine').get(id=plan_id)
            data = {
                'id': plan.id,
                'date': plan.date.strftime('%Y-%m-%d'),
                'line': plan.line.name,
                'machine': plan.machine.name,
                'part': plan.part.name,
                'start_time': plan.start_time.strftime('%H:%M'),
                'end_time': plan.end_time.strftime('%H:%M'),
                'planned_quantity': plan.planned_quantity,
                'sequence': plan.sequence,
                'notes': plan.notes,
                'duration_minutes': plan.duration_minutes,
                'achievement_rate': plan.achievement_rate,
            }
            return JsonResponse(data)
        except Plan.DoesNotExist:
            return JsonResponse({'error': 'Plan not found'}, status=404)


class PlanSequenceUpdateAPIView(LineAccessMixin, View):
    """計画順番更新API"""
    
    def post(self, request, line_id, date_str):
        try:
            import json
            from datetime import datetime
            
            data = json.loads(request.body)
            plan_orders = data.get('plan_orders', [])
            
            # 日付の変換
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': '無効な日付形式です。'}, status=400)
            
            # 順番を更新
            for order_data in plan_orders:
                plan_id = order_data.get('id')
                new_sequence = order_data.get('sequence')
                
                if plan_id and new_sequence:
                    try:
                        plan = Plan.objects.get(id=plan_id, line_id=line_id, date=date_obj)
                        plan.sequence = new_sequence
                        plan.save(update_fields=['sequence'])
                    except Plan.DoesNotExist:
                        continue
            
            return JsonResponse({'success': True, 'message': '順番を更新しました。'})
        
        except json.JSONDecodeError:
            return JsonResponse({'error': '無効なJSONデータです。'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class FeedbackListView(LoginRequiredMixin, ListView):
    """フィードバック一覧"""
    model = Feedback
    template_name = 'production/feedback_list.html'
    context_object_name = 'feedbacks'
    ordering = ['-created_at']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ユーザーの最後に選択したラインを取得
        try:
            user_pref = UserPreference.objects.get(user=self.request.user)
            line = user_pref.last_selected_line
            if line:
                context['line'] = line
                context['date_str'] = timezone.now().strftime('%Y-%m-%d')
        except UserPreference.DoesNotExist:
            pass
        return context

@require_POST
def feedback_submit(request):
    form = FeedbackForm(request.POST, request.FILES)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.user = request.user
        feedback.page_url = request.POST.get('page_url', '')
        feedback.save()
        return JsonResponse({
            'status': 'success',
            'redirect_url': reverse('production:feedback_list')
        })
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors})

@require_POST
@login_required
def feedback_edit(request, pk):
    """フィードバック編集"""
    feedback = get_object_or_404(Feedback, pk=pk)
    
    # スタッフ以外は自分のフィードバックのみ編集可能
    if not request.user.is_staff and feedback.user != request.user:
        return JsonResponse({'error': '権限がありません。'}, status=403)
    
    form = FeedbackEditForm(request.POST, instance=feedback)
    if form.is_valid():
        form.save()
        messages.success(request, 'フィードバックを更新しました。')
        return redirect('production:feedback_list')
    
    messages.error(request, 'フォームの入力内容に問題があります。')
    return redirect('production:feedback_list')

@login_required
def get_new_feedback_count(request):
    """新規フィードバック件数を取得するAPI"""
    count = Feedback.objects.filter(status='new').count()
    return JsonResponse({'count': count})
