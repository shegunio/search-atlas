from celery import shared_task
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.conf import settings


@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass


@shared_task
def check_overdue_loans():
    today = timezone.now().date()
    overdue_loans = Loan.objects.filter(is_returned=False, due_date__lt=today)

    for loan in overdue_loans:
        user = loan.member.user
        email = user.email
        book_title = loan.book.title
        days_overdue = (today - loan.due_date).days

        message = f"""Dear {user.first_name or user.username},

This is to remind you that your book loan for "{book_title}" is overdue by {days_overdue} day(s).

Due Date: {loan.due_date}
Please return the book as soon as possible.

Regards,
Library Management System
"""

        send_mail(
            subject='Overdue Book Loan Reminder',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

