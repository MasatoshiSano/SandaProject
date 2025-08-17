from django import forms
from django.contrib.auth.models import User
from django.db import models
from .models import Plan, Part, Category, Tag, Result, Line, Machine, Feedback
from datetime import date


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ['date', 'line', 'machine', 'part', 'start_time', 'end_time', 'planned_quantity', 'sequence', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'line': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'part': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'planned_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'sequence': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        # 翌日跨ぎの場合は許可（24時間稼働対応）
        # end_time <= start_time の場合は翌日終了とみなす
        pass
        
        # 順番の自動調整
        self._adjust_sequence(cleaned_data)
        
        return cleaned_data
    
    def _adjust_sequence(self, cleaned_data):
        """順番の自動調整を行う"""
        line = cleaned_data.get('line')
        date = cleaned_data.get('date')
        sequence = cleaned_data.get('sequence')
        
        if not (line and date and sequence):
            return
        
        # 同じライン・日付の既存計画を取得
        existing_plans = Plan.objects.filter(line=line, date=date)
        
        # 編集中の計画は除外
        if self.instance and self.instance.pk:
            existing_plans = existing_plans.exclude(pk=self.instance.pk)
        
        max_sequence = existing_plans.aggregate(max_seq=models.Max('sequence'))['max_seq'] or 0
        
        # 大きな数字が入力された場合は最後尾に設定
        if sequence > max_sequence + 1:
            cleaned_data['sequence'] = max_sequence + 1
            return
        
        # 既存の順番と重複する場合の調整
        existing_at_sequence = existing_plans.filter(sequence=sequence).first()
        if existing_at_sequence:
            # 既存の計画の順番を後ろにずらす
            self._shift_sequences(line, date, sequence, existing_plans)
    
    def _shift_sequences(self, line, date, from_sequence, existing_plans):
        """指定した順番以降の計画の順番を後ろにずらす"""
        plans_to_shift = existing_plans.filter(sequence__gte=from_sequence).order_by('sequence')
        
        for plan in plans_to_shift:
            plan.sequence += 1
            plan.save(update_fields=['sequence'])

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        line_id = kwargs.pop('line_id', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # ユーザーがアクセス可能なラインのみ表示
            from .utils import get_accessible_lines
            accessible_lines = get_accessible_lines(user)
            line_ids = [access.line.id for access in accessible_lines]
            self.fields['line'].queryset = Line.objects.filter(id__in=line_ids)
            self.fields['machine'].queryset = Machine.objects.filter(line__id__in=line_ids)
        
        if line_id:
            # ラインが指定されている場合は固定
            self.fields['line'].initial = line_id
            self.fields['line'].widget = forms.HiddenInput()
            self.fields['machine'].queryset = Machine.objects.filter(line_id=line_id)
            # アクティブな機種をすべて表示（ラインに関係なく）
            self.fields['part'].queryset = Part.objects.filter(is_active=True)
        else:
            # ラインが指定されていない場合はアクティブな機種のみ表示
            self.fields['part'].queryset = Part.objects.filter(is_active=True)


class PartForm(forms.ModelForm):
    tags = forms.CharField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = Part
        fields = ['name', 'part_number', 'category', 'target_pph', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'part_number': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'target_pph': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['category'].empty_label = "カテゴリを選択してください"
        
        # 編集時は既存のタグを設定
        if self.instance.pk:
            tag_ids = list(self.instance.tags.values_list('id', flat=True))
            self.fields['tags'].initial = ','.join(map(str, tag_ids))
    
    def save(self, commit=True):
        instance = super().save(commit=commit)
        
        if commit:
            # タグの処理
            tag_ids_str = self.cleaned_data.get('tags', '')
            if tag_ids_str:
                tag_ids = [int(id) for id in tag_ids_str.split(',') if id.strip()]
                tags = Tag.objects.filter(id__in=tag_ids)
                instance.tags.set(tags)
            else:
                instance.tags.clear()
        
        return instance


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        }


class ResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ['line', 'machine', 'part', 'timestamp', 'serial_number', 'judgment']
        widgets = {
            'line': forms.TextInput(attrs={'class': 'form-control'}),
            'machine': forms.TextInput(attrs={'class': 'form-control'}),
            'part': forms.TextInput(attrs={'class': 'form-control'}),
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'judgment': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        line_id = kwargs.pop('line_id', None)
        super().__init__(*args, **kwargs)
        
        # ユーザーがアクセス可能なラインのみ表示
        if user:
            from .utils import get_accessible_lines
            accessible_lines = get_accessible_lines(user)
            line_ids = [access.line.id for access in accessible_lines]
            self.fields['line'].queryset = Line.objects.filter(id__in=line_ids)
            self.fields['machine'].queryset = Machine.objects.filter(line_id__in=line_ids)
            self.fields['part'].queryset = Part.objects.filter(is_active=True)
        
        # 特定のラインが指定されている場合
        if line_id:
            self.fields['line'].initial = line_id
            self.fields['machine'].queryset = Machine.objects.filter(line_id=line_id)
        
        # デフォルト値の設定
        if self.instance.pk:
            if hasattr(self.instance, 'line'):
                self.fields['line'].initial = self.instance.line
            if hasattr(self.instance, 'machine'):
                self.fields['machine'].initial = self.instance.machine
            if hasattr(self.instance, 'part'):
                self.fields['part'].initial = self.instance.part


class LineSelectForm(forms.Form):
    line = forms.ModelChoiceField(
        queryset=Line.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='ライン'
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=date.today,
        label='日付'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            from .utils import get_accessible_lines
            accessible_lines = get_accessible_lines(user)
            self.fields['line'].queryset = Line.objects.filter(
                id__in=[access.line.id for access in accessible_lines]
            )
            self.fields['line'].label_from_instance = lambda obj: f"{obj.name} — {obj.description}"


class ResultFilterForm(forms.Form):
    timestamp_start = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        label='開始日時'
    )
    timestamp_end = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        label='終了日時'
    )
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='計画'
    )
    part = forms.ModelChoiceField(
        queryset=Part.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='機種'
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='機種カテゴリ'
    )
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='設備'
    )
    quantity_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        label='実績数量(最小)'
    )
    quantity_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        label='実績数量(最大)'
    )
    serial_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='シリアル番号'
    )
    judgment = forms.ChoiceField(
        choices=[('', '全て')] + Result.JUDGMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='判定'
    )

    def __init__(self, *args, **kwargs):
        line_id = kwargs.pop('line_id', None)
        super().__init__(*args, **kwargs)
        
        if line_id:
            # 特定ラインの計画のみ表示
            self.fields['plan'].queryset = Plan.objects.filter(line_id=line_id).select_related('line', 'part', 'machine').order_by('-date', 'sequence')
            self.fields['machine'].queryset = Machine.objects.filter(line_id=line_id)
            # 特定ラインで使用されている機種のみ表示
            part_ids = Plan.objects.filter(line_id=line_id).values_list('part_id', flat=True).distinct()
            self.fields['part'].queryset = Part.objects.filter(id__in=part_ids, is_active=True)
            # 特定ラインで使用されている機種カテゴリのみ表示
            category_ids = Part.objects.filter(id__in=part_ids, is_active=True).values_list('category_id', flat=True).distinct()
            self.fields['category'].queryset = Category.objects.filter(id__in=category_ids, is_active=True) 


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['category', 'priority', 'description', 'attachment']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }


class FeedbackEditForm(forms.ModelForm):
    """フィードバック編集フォーム"""
    class Meta:
        model = Feedback
        fields = ['category', 'priority', 'status', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        } 