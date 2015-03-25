import datetime, pprint, mimetypes, os

from django.shortcuts import render, render_to_response, redirect
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.template import RequestContext, loader
from django.db import connection

from django.views.generic import RedirectView
from django.views.decorators.csrf import csrf_exempt

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout


from taskManager.models import Task, Project, Notes, File
from taskManager.misc import *
from taskManager.forms import UserForm, GroupForm, AssignProject, ManageTask, ProjectFileForm, ProfileForm


#pmem can only see his tasks
#pman can only see his projects
#admin can see all tasks

def manage_tasks(request, project_id):

	user  = request.user
	proj = Project.objects.get(pk = project_id)

	if user.is_authenticated():
		logged_in = True

		if user.has_perm('can_change_project'):

			if request.method == 'POST':
				form = ManageTask(request.POST)
				valid = False
				if form.is_valid():
					valid = True
					username_input = form.cleaned_data['User']
					task_input = form.cleaned_data['Task']

					user_tuples = get_my_choices_users()
					task_tuples = get_my_choices_tasks(proj)

					user = User.objects.get(username= user_tuples[int(username_input)-1][1])
					task = Task.objects.get(text = task_tuples[int(task_input)-1][1])

					task.users_assigned.add(user)
					
				return render_to_response('taskManager/manage_tasks.html', 
					{'task':form.errors, 'valid':valid, 'logged_in':logged_in}, RequestContext(request))

			else:   
				form = ManageTask(current_proj = proj)

				return render_to_response('taskManager/manage_tasks.html', 
					{'form':form,'logged_in':logged_in}, RequestContext(request))

		else:
			return redirect('/taskManager/', {'permission':False})
	else:
		redirect('/taskManager/', {'logged_in':False})

def manage_projects(request):

	user  = request.user

	if user.is_authenticated():
		logged_in = True

		if user.has_perm('can_change_group'):

			if request.method == 'POST':
				form = AssignProject(request.POST)
				if form.is_valid():

					username_input = form.cleaned_data['User']
					title_input = form.cleaned_data['Project']

					user_tuples = get_my_choices_users()
					project_tuples = get_my_choices_projects()

					user = User.objects.get(username=user_tuples[int(username_input)-1][1])
					project = Project.objects.get(title = project_tuples[int(title_input)-1][1])

					project.users_assigned.add(user)

				return redirect('/taskManager/')
			else:   

				form = AssignProject()

				return redirect('/taskManager/')

		else:
			return redirect('/taskManager/', {'permission':False})
	else:
		redirect('/taskManager/', {'logged_in':False})

def manage_groups(request):

	user = request.user

	if user.is_authenticated():

		if user.has_perm('can_change_group'):
			
			user_list = User.objects.order_by('date_joined')

			if request.method == 'POST':

				post_data = request.POST.dict()

				accesslevel = post_data["accesslevel"].strip()

				if accesslevel in ['admin_g', 'project_managers', 'team_member']:
					try:
						grp = Group.objects.get(name=accesslevel)
					except:
						grp = Group.objects.create(name=accesslevel)
					user = User.objects.get(pk=post_data["userid"])
					# Check if the user even exists
					if user == None:
						return redirect('/taskManager/', {'permission':False})
					user.groups.add(grp)
					user.save()
					return render_to_response('taskManager/manage_groups.html', 
						{'users':user_list, 'groups_changed': True, 'logged_in':True}, RequestContext(request))
				else:
					return render_to_response('taskManager/manage_groups.html', 
						{'users':user_list, 'logged_in':True}, RequestContext(request))					

			else:	
				return render_to_response('taskManager/manage_groups.html', 
					{'users':user_list, 'logged_in':True}, RequestContext(request))
		else:
			return redirect('/taskManager/', {'permission':False})
	else:
		redirect('/taskManager/', {'logged_in':False})

def new_file(request, project_id):

	if request.method == 'POST':
	   
		proj = Project.objects.get(pk = project_id)
		form = ProjectFileForm(request.POST, request.FILES)

		if form.is_valid():
			name = request.POST.get('name', False)
			upload_path = store_uploaded_file(name, request.FILES['file'])
		   
			file = File(
			name = name,
			path = upload_path,
			project = proj)

			file.save()

			return redirect('/taskManager/' + project_id + '/', {'new_file_added':True})
		else:
			form = ProjectFileForm()
	else:
		form = ProjectFileForm()
	return render_to_response('taskManager/newfile.html', {'form': form}, RequestContext(request))

def download_file(request, file_id):

	file = File.objects.get(pk = file_id)
	abspath = open(os.path.dirname(os.path.realpath(__file__)) + file.path,'rb')
	response = HttpResponse(content=abspath.read())
	response['Content-Type']= mimetypes.guess_type(file.path)[0]
	response['Content-Disposition'] = 'attachment; filename=%s' % file.name
	return response

def download_profile_pic(request, user_id):

	user = User.objects.get(pk = user_id)
	filepath = user.userprofile.image
	return redirect(filepath)
	#filename = user.get_full_name()+"."+filepath.split(".")[-1]
	#try:
	#	abspath = open(filepath, 'rb')
	#except:
	#	abspath = open("./taskmanager"+filepath, 'rb')
	#response = HttpResponse(content=abspath.read())
	#response['Content-Type']= mimetypes.guess_type(filepath)[0]
	#return response

def new_task(request, project_id):

	if request.method == 'POST':
	   
		proj = Project.objects.get(pk = project_id)

		text = request.POST.get('text', False)
		task_title = request.POST.get('task_title', False)
		now = datetime.datetime.now()
		task_duedate = datetime.datetime.fromtimestamp(int(request.POST.get('task_duedate', False)))
	   
		task = Task(
		text = text,
		title = task_title,
		start_date = now,
		due_date = task_duedate,
		project = proj)

		task.save()
		task.users_assigned = [request.user]

		return redirect('/taskManager/' + project_id + '/', {'new_task_added':True})
	else:
		return render_to_response('taskManager/createTask.html', {'proj_id':project_id}, RequestContext(request))

def edit_task(request, project_id, task_id):

	proj = Project.objects.get(pk = project_id)
	task = Task.objects.get(pk = task_id)

	if request.method == 'POST':

		if task.project == proj:

			text = request.POST.get('text', False)
			task_title = request.POST.get('task_title', False)
			task_completed = request.POST.get('task_completed', False)
		   
			task.title = task_title
			task.text = text
			task.completed = True if task_completed == "1" else False
			task.save()

		return redirect('/taskManager/' + project_id + '/' + task_id)
	else:
		return render_to_response('taskManager/editTask.html', {'task': task}, RequestContext(request))

def delete_task(request, project_id, task_id):	   
	proj = Project.objects.get(pk = project_id)
	task = Task.objects.get(pk = task_id)
	if proj != None:
		if task != None and task.project == proj:
			task.delete()

	return redirect('/taskManager/' + project_id + '/')

def complete_task(request, project_id, task_id):
	proj = Project.objects.get(pk = project_id)
	task = Task.objects.get(pk = task_id)
	if proj != None:
		if task != None and task.project == proj:
			task.completed = not task.completed
			task.save()

	return redirect('/taskManager/' + project_id)

def new_project(request):

	if request.method == 'POST':
	   
		title = request.POST.get('title', False)
		text = request.POST.get('text', False)
		project_priority = int(request.POST.get('project_priority', False))
		now = datetime.datetime.now()
		project_duedate = datetime.datetime.fromtimestamp(int(request.POST.get('project_duedate', False)))
	   
		project = Project(title = title,
		text = text,
		priority = project_priority,
		due_date = project_duedate,
		start_date = now)
		project.save()
		project.users_assigned = [request.user.id]
		
		return redirect('/taskManager/', {'new_project_added':True})
	else:
		return render_to_response('taskManager/createProject.html', {}, RequestContext(request))

def edit_project(request, project_id):

	proj = Project.objects.get(pk = project_id)

	if request.method == 'POST':

		title = request.POST.get('title', False)
		text = request.POST.get('text', False)
		project_priority = int(request.POST.get('project_priority', False))
		project_duedate = datetime.datetime.fromtimestamp(int(request.POST.get('project_duedate', False)))
	   
		proj.title = title
		proj.text = text
		proj.priority = project_priority
		proj.due_date = project_duedate
		proj.save()

		return redirect('/taskManager/' + project_id + '/')
	else:
		return render_to_response('taskManager/editProject.html', {'proj': proj}, RequestContext(request))

def delete_project(request, project_id):
	# IDOR
	project = Project.objects.get(pk=project_id)
	project.delete()
	return redirect('/taskManager/dashboard')

def logout_view(request):
	logout(request)
	project_list = Project.objects.order_by('-start_date')
	return redirect('/taskManager')

def login_view(request):
	if request.method == 'POST':
		username = request.POST.get('username', False)
		password = request.POST.get('password', False)

		user = authenticate(username=username, password=password)
		if user is not None:
			if user.is_active:
				login(request, user)
				# Redirect to a success page.
				return redirect('/taskManager/')
			else:
				# Return a 'disabled account' error message
				return redirect('/taskManager/', {'disabled_user':True})
		else:
			# Return an 'invalid login' error message.
			return render(request, 'taskManager/login.html', {'failed_login': False})
	else:
		return render_to_response('taskManager/login.html', {}, RequestContext(request))

def register(request):

	context = RequestContext(request)

	registered = False

	if request.method == 'POST':

		user_form = UserForm(data=request.POST)

		# If the two forms are valid...
		if user_form.is_valid():
			# Save the user's form data to the database.
			user = user_form.save()

			user.set_password(user.password)

			#add user to lowest permission group
			#grp = Group.objects.get(name='team_member')
			#user.groups.add(grp)

			user.save()

			# Update our variable to tell the template registration was successful.
			registered = True
		
		#else:
		 #   print user_form.errors

	# Not a HTTP POST, so we render our form using two ModelForm instances.
	# These forms will be blank, ready for user input.
	else:
		user_form = UserForm()

	# Render the template depending on the context.
	return render_to_response(
			'taskManager/register.html',
			{'user_form': user_form, 'registered': registered},
			context)

def index(request):
	project_list = Project.objects.order_by('-start_date')
	
	admin_level = False

	if request.user.groups.filter(name='admin_g').exists():
		admin_level = True

	list_to_show = []
	for project in project_list:
		if(project.users_assigned.filter(username= request.user.username)).exists():
			list_to_show.append(project)

	if request.user.is_authenticated():
		  return redirect("/taskManager/dashboard")
	else:
		return render(
			request, 
			'taskManager/index.html', 
			{'project_list': project_list, 
			'user':request.user , 
			'admin_level':admin_level }
			)	

def proj_details(request, project_id):
	proj = Project.objects.filter(users_assigned = request.user.id, pk = project_id)
	if not proj:
	  messages.warning(request, 'You are not authorized to view this project')
	  return redirect('/taskManager/dashboard')
	else:
	  proj = Project.objects.get(pk=project_id)

	  return render(request, 'taskManager/proj_details.html', {'proj': proj})

def new_note(request, project_id, task_id):
	if request.method == 'POST':
	   
		parent_task = Task.objects.get(pk = task_id)

		note_title = request.POST.get('note_title', False)
		text = request.POST.get('text', False)
		now = datetime.datetime.now()
	   
		note = Notes(
		title = note_title,
		text = text,
		user = request.user,
		task = parent_task)

		note.save()
		return redirect('/taskManager/' + project_id + '/' + task_id, {'new_note_added':True})
	else:
		return render_to_response('taskManager/createNote.html', {'task_id':task_id}, RequestContext(request))

def edit_note(request, project_id, task_id, note_id):

	proj = Project.objects.get(pk = project_id)
	task = Task.objects.get(pk = task_id)
	note = Notes.objects.get(pk = note_id)

	if request.method == 'POST':

		if task.project == proj:

			if note.task == task:

				text = request.POST.get('text', False)
				note_title = request.POST.get('note_title', False)
			   
				note.title = note_title
				note.text = text
				note.save()

		return redirect('/taskManager/' + project_id + '/' + task_id)
	else:
		return render_to_response('taskManager/editNote.html', {'note': note}, RequestContext(request))

def delete_note(request, project_id, task_id, note_id):	   
	proj = Project.objects.get(pk = project_id)
	task = Task.objects.get(pk = task_id)
	note = Notes.objects.get(pk = note_id)
	if proj != None:
		if task != None and task.project == proj:
			if note != None and note.task == task:
				note.delete()

	return redirect('/taskManager/' + project_id + '/' + task_id)

def task_details(request, project_id, task_id):

	task = Task.objects.get(pk = task_id)

	logged_in = True

	if not request.user.is_authenticated():
		logged_in =False

	admin_level = False
	if request.user.groups.filter(name='admin_g').exists():
		admin_level = True

	pmanager_level = False
	if request.user.groups.filter(name='project_managers').exists():
		pmanager_level = True

	assigned_to = False
	if task.users_assigned.filter(username= request.user.username).exists():
		assigned_to = True
	elif admin_level == True:
		assigned_to = True
	elif pmanager_level == True and proj.users_assigned.filter(username= request.user.username).exists():
		assigned_to = True

	return render(request, 'taskManager/task_details.html', {'task':task, 'assigned_to':assigned_to, 'logged_in':logged_in, 'completed_task': "Yes" if task.completed else "No"})

def dashboard(request):
	project_list = Project.objects.order_by('-start_date')
	return render(request, 'taskManager/dashboard.html',  {'project_list': project_list, 'user':request.user })

def my_projects(request):
	project_list = Project.objects.filter(users_assigned=request.user.id)
	return render(request, 'taskManager/dashboard.html',  {'project_list': project_list, 'user':request.user })

def my_tasks(request):
	my_task_list = Task.objects.filter(users_assigned=request.user.id)
	return render(request, 'taskManager/mytasks.html',  {'task_list': my_task_list, 'user':request.user })

def search(request):
	q =  request.GET.get('q')
	if not q: q = ''
	my_project_list = Project.objects.filter(users_assigned=request.user.id).filter(title__icontains=q).order_by('title')
	my_task_list = Task.objects.filter(users_assigned=request.user.id).filter(title__icontains=q).order_by('title')
	return render(request, 'taskManager/search.html',  {'q':q, 'task_list':my_task_list, 'project_list':my_project_list, 'user':request.user })

def tutorials(request):
	return render(request, 'taskManager/tutorials.html', {'user':request.user})
	
def show_tutorial(request, vuln_id):
	if vuln_id in ["injection", "brokenauth", "xss", "idor", "misconfig", "exposure", "access", "csrf", "components", "redirects"]:
		return render(request, 'taskManager/tutorials/' + vuln_id+'.html')
	else:
		return render(request, 'taskManager/tutorials.html', {'user':request.user});

def profile(request):
	return render(request,'taskManager/profile.html',{'user':request.user})

@csrf_exempt
def profile_by_id(request, user_id):
	user = User.objects.get(pk = user_id)

	if request.method == 'POST':
		form = ProfileForm(request.POST, request.FILES)
		if form.is_valid():
			print("made it!")
			if request.POST.get('first_name') != user.first_name:
				user.first_name = request.POST.get('first_name')
			if request.POST.get('last_name') != user.last_name:
				user.last_name = request.POST.get('last_name')
			if request.POST.get('email') != user.email:
				user.email = request.POST.get('email')
			if request.POST.get('password'):
				user.set_password(request.POST.get('password'))
			user.userprofile.image = store_uploaded_file(user.get_full_name()+"."+request.FILES['picture'].name.split(".")[-1], request.FILES['picture'])
			user.userprofile.save()
			user.save()
			messages.info(request, "User Updated")

	return render(request,'taskManager/profile.html',{'user':user})

@csrf_exempt
def change_password(request):
	
	if request.method == 'POST':
		user = request.user
		old_password = request.POST.get('old_password')
		new_password = request.POST.get('new_password')
		confirm_passwrd = request.POST.get('confirm_password')
		
		u = authenticate(username=user.username, password=old_password)
		if u is not None:
			if new_password == confirm_passwrd:
				user.set_password(new_password)
				user.save()
				messages.success(request,'Password Updated')
			else:
				messages.warning(request,'Passwords do not match')
		else:
			messages.warning(request,'Invalid Password')
	
	return render(request,'taskManager/change_password.html',{'user':request.user})
