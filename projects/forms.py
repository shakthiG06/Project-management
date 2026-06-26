from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile, Project, Task, Milestone, Document, Comment

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email Address")
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, required=True, label="Select Role")
    
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-input'

    def save(self, commit=True):
        user = super().save(commit=commit)
        role = self.cleaned_data.get('role')
        if commit:
            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
        return user

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'start_date', 'end_date', 'status', 'members']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'name': forms.TextInput(attrs={'placeholder': 'Project Name', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'placeholder': 'Describe the project goals...', 'rows': 4, 'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'members': forms.SelectMultiple(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate members with all users, option to exclude managers if desired
        self.fields['members'].queryset = User.objects.all().exclude(is_superuser=True)
        self.fields['members'].label_from_instance = lambda obj: f"{obj.username} ({getattr(obj, 'profile', None).get_role_display() if getattr(obj, 'profile', None) else 'No Profile'})"

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'priority', 'due_date', 'assigned_to', 'milestone']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'title': forms.TextInput(attrs={'placeholder': 'Task Title', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'placeholder': 'Describe the task responsibilities...', 'rows': 3, 'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'priority': forms.Select(attrs={'class': 'form-input'}),
            'assigned_to': forms.Select(attrs={'class': 'form-input'}),
            'milestone': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        if project:
            # Filter assigned_to to only members of the project + the manager
            project_members = list(project.members.all())
            if project.manager not in project_members:
                project_members.append(project.manager)
            self.fields['assigned_to'].queryset = User.objects.filter(id__in=[m.id for m in project_members])
            # Filter milestones to this project only
            self.fields['milestone'].queryset = Milestone.objects.filter(project=project)
        else:
            self.fields['assigned_to'].queryset = User.objects.all()
            self.fields['milestone'].queryset = Milestone.objects.all()
            
        self.fields['assigned_to'].label_from_instance = lambda obj: f"{obj.username} ({getattr(obj, 'profile', None).get_role_display() if getattr(obj, 'profile', None) else 'No Profile'})"

class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ['title', 'description', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'title': forms.TextInput(attrs={'placeholder': 'Milestone Title', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'placeholder': 'Describe milestone goals...', 'rows': 2, 'class': 'form-input'}),
        }

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Document Title (e.g. Spec, Diagram)', 'class': 'form-input'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-input-file'}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'placeholder': 'Add a comment...', 'rows': 2, 'class': 'form-input'}),
        }
