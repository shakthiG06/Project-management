from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

from .models import Profile, Project, Task, Milestone, Comment, Document, Notification
from .forms import UserRegistrationForm, ProjectForm, TaskForm, MilestoneForm, DocumentForm, CommentForm

# Helpers
def create_notification(user, message):
    Notification.objects.create(user=user, message=message)

# Role check decorators
def manager_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not hasattr(request.user, 'profile') or request.user.profile.role != 'manager':
            messages.error(request, "Access Denied: Only Project Managers can perform this action.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def project_member_required(view_func):
    def _wrapped_view_func(request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        project = get_object_or_404(Project, pk=pk)
        is_manager = (project.manager == request.user)
        is_member = project.members.filter(id=request.user.id).exists()
        if not (is_manager or is_member):
            messages.error(request, "Access Denied: You are not a member of this project.")
            return redirect('dashboard')
        return view_func(request, pk, *args, **kwargs)
    return _wrapped_view_func

# Auth Views
def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful. Welcome to PMS!")
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'projects/signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'projects/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "You have logged out successfully.")
    return redirect('login')

# Dashboard View
@login_required
def dashboard(request):
    profile = get_object_or_404(Profile, user=request.user)
    query = request.GET.get('q', '')
    
    # Filter projects based on role
    if profile.role == 'manager':
        projects = Project.objects.filter(manager=request.user).order_by('-created_at')
    else:
        projects = Project.objects.filter(members=request.user).order_by('-created_at')
    if query:
        projects= projects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query)
    )
        
    # Get active tasks in user's projects
    if profile.role == 'manager':
        tasks = Task.objects.filter(project__manager=request.user).order_by('-updated_at')
    else:
        tasks = Task.objects.filter(project__members=request.user).order_by('-updated_at')

    if query:
        tasks = tasks.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query)
    )
        
    assigned_tasks = Task.objects.filter(assigned_to=request.user).order_by('due_date')
    
    # Count stats
    total_projects = projects.count()
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    pending_tasks = total_tasks - completed_tasks
    
    # Notifications
    unread_notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')
    unread_count = unread_notifications.count()
    
    # Recent Activities (e.g. comments, tasks updated)
    # We can fetch last 5 tasks updated
    recent_tasks = tasks[:5]
    
    context = {
        'profile': profile,
        'projects': projects,
        'assigned_tasks': assigned_tasks,
        'total_projects': total_projects,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'unread_notifications': unread_notifications[:5],
        'unread_count': unread_count,
        'recent_tasks': recent_tasks,
        'query': query,
    }
    return render(request, 'projects/dashboard.html', context)

# Project Views
@login_required
@manager_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.manager = request.user
            project.save()
            form.save_m2m() # Save ManyToMany members
            
            # Send notifications to members
            for member in project.members.all():
                create_notification(member, f"You have been added to a new project: {project.name}.")
                
            messages.success(request, f"Project '{project.name}' created successfully!")
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Create Project'})

@login_required
@project_member_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    milestones = project.milestones.all().order_by('due_date')
    tasks = project.tasks.all().order_by('due_date')
    documents = project.documents.all().order_by('-uploaded_at')
    
    # Statistics for the project
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    percentage = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
    
    context = {
        'project': project,
        'milestones': milestones,
        'tasks': tasks,
        'documents': documents,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'progress_percentage': percentage,
        'is_manager': project.manager == request.user,
        'comment_form': CommentForm(),
        'document_form': DocumentForm(),
    }
    return render(request, 'projects/project_detail.html', context)

@login_required
@manager_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.manager != request.user:
        messages.error(request, "Permission Denied: You are not the manager of this project.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            old_members = set(project.members.all())
            project = form.save()
            new_members = set(project.members.all())
            
            # Notify newly added members
            added_members = new_members - old_members
            for member in added_members:
                create_notification(member, f"You have been added to project: {project.name}.")
                
            messages.success(request, f"Project '{project.name}' updated successfully!")
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, 'projects/project_form.html', {'form': form, 'title': f'Edit {project.name}', 'project': project})

@login_required
@manager_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.manager != request.user:
        messages.error(request, "Permission Denied: You are not the manager of this project.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f"Project '{name}' deleted successfully.")
        return redirect('dashboard')
    return render(request, 'projects/project_confirm_delete.html', {'project': project})

# Milestone Views
@login_required
@manager_required
def milestone_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.manager != request.user:
        messages.error(request, "Permission Denied: You are not the manager of this project.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = MilestoneForm(request.POST)
        if form.is_valid():
            milestone = form.save(commit=False)
            milestone.project = project
            milestone.save()
            
            # Notify members
            for member in project.members.all():
                create_notification(member, f"New milestone '{milestone.title}' added to project '{project.name}'.")
                
            messages.success(request, f"Milestone '{milestone.title}' created successfully!")
            return redirect('project_detail', pk=project.pk)
    else:
        form = MilestoneForm()
    return render(request, 'projects/milestone_form.html', {'form': form, 'project': project})

@login_required
@manager_required
def milestone_toggle(request, project_id, milestone_id):
    project = get_object_or_404(Project, pk=project_id)
    if project.manager != request.user:
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    milestone = get_object_or_404(Milestone, pk=milestone_id, project=project)
    milestone.is_achieved = not milestone.is_achieved
    milestone.save()
    
    status_str = "achieved" if milestone.is_achieved else "not achieved"
    # Notify members
    for member in project.members.all():
        create_notification(
            member,
            f"Milestone '{milestone.title}' status updated to {status_str} in '{project.name}'."
        )

    messages.success(request, f"Milestone status updated to {status_str}.")
    return redirect('project_detail', pk=project.pk)

# Task Views
@login_required
@manager_required
def task_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.manager != request.user:
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.created_by = request.user
            task.save()
            
            # Notify assignee
            if task.assigned_to:
                create_notification(task.assigned_to, f"You have been assigned a new task: '{task.title}' in '{project.name}'.")
            
            messages.success(request, f"Task '{task.title}' created successfully!")
            return redirect('project_detail', pk=project.pk)
    else:
        form = TaskForm(project=project)
    return render(request, 'projects/task_form.html', {'form': form, 'project': project, 'title': 'Create Task'})

@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    project = task.project
    
    # Check project membership
    is_manager = (project.manager == request.user)
    is_member = project.members.filter(id=request.user.id).exists()
    if not (is_manager or is_member):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    comments = task.comments.all().order_by('-created_at')
    comment_form = CommentForm()
    
    context = {
        'task': task,
        'comments': comments,
        'comment_form': comment_form,
        'is_manager': is_manager,
        'is_assignee': task.assigned_to == request.user,
    }
    return render(request, 'projects/task_detail.html', context)

@login_required
@manager_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    project = task.project
    if project.manager != request.user:
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        old_assignee = task.assigned_to
        form = TaskForm(request.POST, instance=task, project=project)
        if form.is_valid():
            task = form.save()
            # Notify assignee if changed
            if task.assigned_to and task.assigned_to != old_assignee:
                create_notification(task.assigned_to, f"You have been assigned task: '{task.title}' in '{project.name}'.")
            messages.success(request, "Task updated successfully!")
            return redirect('task_detail', pk=task.pk)
    else:
        form = TaskForm(instance=task, project=project)
    return render(request, 'projects/task_form.html', {'form': form, 'project': project, 'title': f'Edit {task.title}', 'task': task})

@login_required
def task_status_update(request, pk):
    task = get_object_or_404(Task, pk=pk)
    project = task.project
    
    # Only assignee or manager can update task status
    is_manager = (project.manager == request.user)
    is_assignee = (task.assigned_to == request.user)
    if not (is_manager or is_assignee):
        messages.error(request, "Permission Denied: You cannot update this task status.")
        return redirect('task_detail', pk=task.pk)
        
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Task.STATUS_CHOICES):
            old_status = task.get_status_display()
            task.status = new_status
            task.save()
            
            # Notify relevant party
            status_display = task.get_status_display()
            msg = f"Task '{task.title}' status changed from '{old_status}' to '{status_display}' by {request.user.username}."
            if is_assignee:
                # Notify manager
                create_notification(project.manager, msg)
            elif is_manager and task.assigned_to:
                # Notify assignee
                create_notification(task.assigned_to, msg)
                
            messages.success(request, f"Task status updated to '{status_display}'.")
    return redirect('task_detail', pk=task.pk)

@login_required
def comment_add(request, pk):
    task = get_object_or_404(Task, pk=pk)
    project = task.project
    is_manager = (project.manager == request.user)
    is_member = project.members.filter(id=request.user.id).exists()
    if not (is_manager or is_member):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.user = request.user
            comment.save()
            
            # Notify assignee and manager (exclude self)
            msg = f"{request.user.username} commented on task '{task.title}': '{comment.content[:30]}...'"
            if task.assigned_to and task.assigned_to != request.user:
                create_notification(task.assigned_to, msg)
            if project.manager != request.user:
                create_notification(project.manager, msg)
                
            messages.success(request, "Comment added.")
    return redirect('task_detail', pk=task.pk)

# Document Views
@login_required
def document_upload(request, pk):
    project = get_object_or_404(Project, pk=pk)
    is_manager = (project.manager == request.user)
    is_member = project.members.filter(id=request.user.id).exists()
    if not (is_manager or is_member):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.project = project
            doc.uploaded_by = request.user
            doc.save()
            
            # Notify members
            for member in project.members.all():
                if member != request.user:
                    create_notification(member, f"{request.user.username} uploaded a document: '{doc.title}' in '{project.name}'.")
            if project.manager != request.user:
                create_notification(project.manager, f"{request.user.username} uploaded a document: '{doc.title}' in '{project.name}'.")
                
            messages.success(request, f"Document '{doc.title}' uploaded successfully!")
    return redirect('project_detail', pk=project.pk)

@login_required
def document_delete(request, project_id, document_id):
    project = get_object_or_404(Project, pk=project_id)
    doc = get_object_or_404(Document, pk=document_id, project=project)
    
    # Manager or owner can delete
    if project.manager == request.user or doc.uploaded_by == request.user:
        name = doc.title
        doc.delete()
        messages.success(request, f"Document '{name}' deleted.")
    else:
        messages.error(request, "Permission Denied to delete this document.")
    return redirect('project_detail', pk=project.pk)

# Notification Views
@login_required
def notifications_list(request):
    notifications = request.user.notifications.all().order_by('-created_at')
    return render(request, 'projects/notifications.html', {'notifications': notifications})

@login_required
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('notifications_list')

# Reports View
@login_required
def reports_view(request):
    profile = request.user.profile
    if profile.role == 'manager':
        projects = Project.objects.filter(manager=request.user)
        project_ids = [p.id for p in projects]
        tasks = Task.objects.filter(project_id__in=project_ids)
    else:
        projects = Project.objects.filter(members=request.user)
        project_ids = [p.id for p in projects]
        tasks = Task.objects.filter(project_id__in=project_ids)
        
    # Task status breakdown
    status_counts = tasks.values('status').annotate(count=Count('id'))
    status_dict = {'todo': 0, 'in_progress': 0, 'review': 0, 'completed': 0}
    for item in status_counts:
        status_dict[item['status']] = item['count']
        
    # Task priority breakdown
    priority_counts = tasks.values('priority').annotate(count=Count('id'))
    priority_dict = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
    for item in priority_counts:
        priority_dict[item['priority']] = item['count']
        
    # Project completion rates
    project_completion_list = []
    for p in projects:
        t_all = p.tasks.count()
        t_done = p.tasks.filter(status='completed').count()
        pct = int(t_done / t_all * 100) if t_all > 0 else 0
        project_completion_list.append({
            'name': p.name,
            'total_tasks': t_all,
            'completed_tasks': t_done,
            'percentage': pct
        })
        
    # Team workload: Tasks completed/pending by member
    # Get distinct members involved in user's projects
    members_workload = []
    if len(project_ids) > 0:
        # Fetch all unique users across these projects
        members_query = User.objects.filter(Q(projects__id__in=project_ids) | Q(managed_projects__id__in=project_ids)).distinct()
        for member in members_query:
            # tasks assigned to this member in user's projects
            m_tasks = tasks.filter(assigned_to=member)
            m_total = m_tasks.count()
            if m_total > 0:
                m_done = m_tasks.filter(status='completed').count()
                members_workload.append({
                    'username': member.username,
                    'total': m_total,
                    'completed': m_done,
                    'pending': m_total - m_done
                })
                
    context = {
        'status_data': status_dict,
        'priority_data': priority_dict,
        'project_completion': project_completion_list,
        'members_workload': members_workload,
        'total_tasks': tasks.count(),
        'total_projects': projects.count(),
    }
    return render(request, 'projects/reports.html', context)
