from django.contrib import admin
from django import forms
from .models import (
    Line, UserLineAccess, Machine, Category, Tag, Part, Plan, Result,
    PartChangeDowntime, WorkCalendar, WorkingDay, DashboardCardSetting, UserPreference,
    PlannedHourlyProduction, Feedback
)


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']


@admin.register(UserLineAccess)
class UserLineAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'line', 'created_at']
    list_filter = ['line', 'created_at']
    search_fields = ['user__username', 'line__name']


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'line', 'is_active', 'is_production_active',  # モデルフィールドを表示
        'active_status', 'production_status', 'created_at'
    ]
    list_filter = ['line', 'is_active', 'is_production_active', 'created_at']
    list_editable = ['is_production_active']
    search_fields = ['name', 'line__name']
    ordering = ['line', 'name']
    
    fieldsets = [
        ('基本情報', {
            'fields': ['name', 'line', 'description']
        }),
        ('設定', {
            'fields': ['is_active', 'is_production_active'],
            'description': 'is_production_active: この設備が現在生産稼働中かを示すフラグです。実績集計の対象になります。'
        }),
        ('履歴', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def active_status(self, obj):
        if obj.is_active:
            return "✅ 有効"
        return "❌ 無効"
    active_status.short_description = '状態'
    
    def production_status(self, obj):
        if obj.is_production_active:
            return "🟢 稼働中"
        return "⚪ 停止中"
    production_status.short_description = '生産状況'
    
    def get_list_display_links(self, request, list_display):
        # list_editable があるフィールドをリンクから除外
        return ['name']  # name フィールドのみをリンクに


class ColorPickerWidget(forms.TextInput):
    """HTML5 の color input ウィジェット"""
    input_type = 'color'


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
        widgets = {
            'color': ColorPickerWidget(),  # color フィールドにカラーピッカーを設定
        }


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm      # ← ここでフォームを指定
    list_display = ['name', 'color', 'created_at']
    list_filter  = ['created_at']
    search_fields = ['name']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name']


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'target_pph', 'cycle_time', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'category__name']
    filter_horizontal = ['tags']
    readonly_fields = ['cycle_time']


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['date', 'line', 'machine', 'sequence', 'part', 'planned_quantity', 'created_at']
    list_filter = ['date', 'line', 'machine', 'part', 'created_at']
    search_fields = ['part__name', 'line__name', 'machine__name']
    ordering = ['date', 'line', 'sequence']


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'line', 'machine', 'part', 'quantity', 'serial_number', 'judgment']
    list_filter = ['line', 'machine', 'part', 'judgment', 'timestamp']
    search_fields = ['serial_number', 'part__name', 'line__name', 'machine__name']
    date_hierarchy = 'timestamp'


@admin.register(PartChangeDowntime)
class PartChangeDowntimeAdmin(admin.ModelAdmin):
    list_display = ['line', 'from_part', 'to_part', 'downtime_seconds', 'created_at']
    list_filter = ['line', 'created_at']
    search_fields = ['line__name', 'from_part__name', 'to_part__name']


@admin.register(WorkCalendar)
class WorkCalendarAdmin(admin.ModelAdmin):
    list_display = ['line', 'work_start_time', 'morning_meeting_duration', 'created_at']
    list_filter = ['created_at']
    search_fields = ['line__name']


@admin.register(WorkingDay)
class WorkingDayAdmin(admin.ModelAdmin):
    list_display = ['date', 'is_working', 'description']
    list_filter = ['is_working', 'date']
    search_fields = ['description']
    date_hierarchy = 'date'


@admin.register(DashboardCardSetting)
class DashboardCardSettingAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_visible', 'order', 'alert_threshold_yellow', 'alert_threshold_red']
    list_filter = ['is_visible']
    search_fields = ['name']
    ordering = ['order', 'name']


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'last_selected_line', 'theme', 'created_at']
    list_filter = ['theme', 'last_selected_line', 'created_at']
    search_fields = ['user__username']


@admin.register(PlannedHourlyProduction)
class PlannedHourlyProductionAdmin(admin.ModelAdmin):
    list_display = ['date', 'line', 'part', 'actual_hour', 'is_next_day', 'planned_quantity', 'working_seconds', 'planned_pph']
    list_filter = ['date', 'line', 'part']
    search_fields = ['line__name', 'part__name']
    date_hierarchy = 'date'
    ordering = ['date', 'line', 'hour']
    readonly_fields = ['actual_hour', 'is_next_day', 'planned_pph']
    
    def actual_hour(self, obj):
        return f"{obj.actual_hour:02d}:00"
    actual_hour.short_description = '実際の時間'
    
    def is_next_day(self, obj):
        return "翌日" if obj.is_next_day else "当日"
    is_next_day.short_description = '日付区分'
    
    def planned_pph(self, obj):
        return obj.planned_pph
    planned_pph.short_description = '計画PPH'


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'get_category_display', 'priority', 'status', 'user', 
        'description_preview', 'created_at', 'updated_at'
    ]
    list_filter = ['category', 'priority', 'status', 'created_at', 'updated_at']
    search_fields = ['description', 'user__username', 'page_url']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('基本情報', {
            'fields': ['user', 'category', 'priority', 'status']
        }),
        ('内容', {
            'fields': ['description', 'attachment', 'page_url']
        }),
        ('履歴', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def description_preview(self, obj):
        """説明文の先頭50文字を表示"""
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_preview.short_description = '内容プレビュー'
    
    def get_category_display(self, obj):
        """カテゴリを日本語表示"""
        return obj.get_category_display()
    get_category_display.short_description = 'カテゴリ'
    
    def get_queryset(self, request):
        """関連オブジェクトを最適化して取得"""
        return super().get_queryset(request).select_related('user')
    
    def has_delete_permission(self, request, obj=None):
        """スタッフのみ削除可能"""
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        """スタッフのみ編集可能"""
        return request.user.is_staff
    
    actions = ['mark_as_completed', 'mark_as_in_review', 'mark_as_rejected']
    
    def mark_as_completed(self, request, queryset):
        """選択したフィードバックを完了状態にする"""
        count = queryset.update(status='completed')
        self.message_user(request, f'{count}件のフィードバックを完了状態に変更しました。')
    mark_as_completed.short_description = '選択したフィードバックを完了状態にする'
    
    def mark_as_in_review(self, request, queryset):
        """選択したフィードバックを確認中状態にする"""
        count = queryset.update(status='in_review')
        self.message_user(request, f'{count}件のフィードバックを確認中状態に変更しました。')
    mark_as_in_review.short_description = '選択したフィードバックを確認中状態にする'
    
    def mark_as_rejected(self, request, queryset):
        """選択したフィードバックを却下状態にする"""
        count = queryset.update(status='rejected')
        self.message_user(request, f'{count}件のフィードバックを却下状態に変更しました。')
    mark_as_rejected.short_description = '選択したフィードバックを却下状態にする'
