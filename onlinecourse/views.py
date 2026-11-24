from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponseNotAllowed
from django.contrib.auth.decorators import login_required
from .models import Course, Enrollment, Question, Choice, Submission
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = User.objects.filter(username=username).exists()
        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect("onlinecourse:index")
        context['message'] = "User already exists."
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        context['message'] = "Invalid username or password."
    return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    if not user.is_authenticated:
        return False
    return Enrollment.objects.filter(user=user, course=course).exists()


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if request.user.is_authenticated:
        Enrollment.objects.get_or_create(user=request.user, course=course)
        course.total_enrollment = Enrollment.objects.filter(course=course).count()
        course.save(update_fields=['total_enrollment'])
    return HttpResponseRedirect(reverse(
        viewname='onlinecourse:course_details', args=(course.id,)
    ))


def extract_answers(request):
    """Collect choice IDs posted by the assessment form."""
    answer_ids = set()
    for key, values in request.POST.lists():
        if key.startswith('choice'):
            for value in values:
                try:
                    answer_ids.add(int(value))
                except (TypeError, ValueError):
                    continue
    return answer_ids


@login_required
def submit(request, course_id):
    """Save the signed-in learner's answers and redirect to the results."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    course = get_object_or_404(Course, pk=course_id)
    enrollment, _ = Enrollment.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={'mode': Enrollment.HONOR}
    )
    questions = Question.objects.filter(
        course=course
    ).prefetch_related('choice_set').order_by('pk')

    valid_choices = Choice.objects.filter(
        question__in=questions,
        pk__in=extract_answers(request)
    )
    submission = Submission.objects.create(enrollment=enrollment)
    submission.choices.set(valid_choices)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.pk,
        submission_id=submission.pk
    )


@login_required
def show_exam_result(request, course_id, submission_id):
    """Calculate the exam score and render feedback for each question."""
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(
        Submission.objects.prefetch_related('choices'),
        pk=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )
    questions = Question.objects.filter(
        course=course
    ).prefetch_related('choice_set').order_by('pk')

    selected_ids = set(submission.choices.values_list('pk', flat=True))
    results = []
    earned = 0
    total = 0

    for question in questions:
        choices = list(question.choice_set.all())
        selected = [choice for choice in choices if choice.pk in selected_ids]
        correct = question.is_get_score(selected)
        points = question.grade
        score = points if correct else 0
        total += points
        earned += score
        results.append({
            'question': question,
            'choices': choices,
            'selected_choices': selected,
            'is_correct': correct,
            'score': score,
            'grade': points,
        })

    grade = round((earned / total) * 100) if total else 0
    return render(request, 'onlinecourse/exam_result_bootstrap.html', {
        'course': course,
        'results': results,
        'earned': earned,
        'total': total,
        'grade': grade,
        'passed': bool(total) and grade >= 70,
        'correct_count': sum(result['is_correct'] for result in results),
        'selected_ids': list(selected_ids),
    })
