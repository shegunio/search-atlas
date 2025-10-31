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
    """
    Query all loans where is_returned is False and due_date is past.
    Send an email reminder to each member with overdue books.
    :return:
    """

    today = timezone.now().date()
    loans = Loan.objects.filter(is_returned=False,)
    print(f'Found {loans.count()} that are not returned yet')

    for loan in loans:
        if loan.due_date < today:
            user = loan.member.user
            email = user.email
            content = f"""
            Dear {user.first_name},
            
            This is to remind you that your book loan is due today, kindly return the book as soon as possible.
            
            Regards,
            SearchAtlas.
            """
            # Send email to user for reminder
            send_mail(
                subject='Loan due date reminder',
                message=content,
                html_message=content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email]
            )

