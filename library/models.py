from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import  timedelta


class Author(models.Model):
    first_name = models.CharField(max_length=100, db_index=True)
    last_name = models.CharField(max_length=100, db_index=True)
    biography = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['first_name', 'last_name']),
        ]
        ordering = ['id']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Book(models.Model):
    GENRE_CHOICES = [
        ('fiction', 'Fiction'),
        ('nonfiction', 'Non-Fiction'),
        ('sci-fi', 'Sci-Fi'),
        ('biography', 'Biography'),
        # Add more genres as needed
    ]

    title = models.CharField(max_length=200, db_index=True)
    author = models.ForeignKey(Author, related_name='books', on_delete=models.CASCADE, db_index=True)
    isbn = models.CharField(max_length=13, unique=True, db_index=True)
    genre = models.CharField(max_length=50, choices=GENRE_CHOICES, db_index=True)
    available_copies = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=['title', 'author']),
            models.Index(fields=['genre', 'available_copies']),
        ]
        ordering = ['id']

    def __str__(self):
        return self.title

class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    membership_date = models.DateField(auto_now_add=True)
    # Add more fields if necessary

    def __str__(self):
        return self.user.username

class Loan(models.Model):
    book = models.ForeignKey(Book, related_name='loans', on_delete=models.CASCADE, db_index=True)
    member = models.ForeignKey(Member, related_name='loans', on_delete=models.CASCADE, db_index=True)
    loan_date = models.DateField(auto_now_add=True, db_index=True)
    return_date = models.DateField(null=True, blank=True)
    is_returned = models.BooleanField(default=False, db_index=True)
    loan_duration = models.IntegerField(default=14)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_returned', 'loan_date']),
            models.Index(fields=['member', 'is_returned']),
            models.Index(fields=['book', 'is_returned']),
        ]
        ordering = ['-loan_date']

    def __str__(self):
        return f"{self.book.title} loaned to {self.member.user.username}"

    def save(self):
        if not self.due_date:
            self.set_default_due_date()
        super().save()

    def set_default_due_date(self):
        if not self.due_date:
            self.due_date = self.loan_date + timedelta(days=self.loan_duration)
            self.save()
