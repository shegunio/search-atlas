from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from .models import Author, Book, Member, Loan
from .tasks import send_loan_notification, check_overdue_loans


class AuthorViewSetTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Author.objects.create(
            first_name="John",
            last_name="Doe",
            biography="Test biography"
        )

    def test_list_authors(self):
        response = self.client.get('/api/authors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_author(self):
        data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'biography': 'Another biography'
        }
        response = self.client.post('/api/authors/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Author.objects.count(), 2)

    def test_retrieve_author(self):
        response = self.client.get(f'/api/authors/{self.author.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'John')

    def test_update_author(self):
        data = {'first_name': 'Johnny', 'last_name': 'Doe', 'biography': 'Updated'}
        response = self.client.put(f'/api/authors/{self.author.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.author.refresh_from_db()
        self.assertEqual(self.author.first_name, 'Johnny')

    def test_delete_author(self):
        response = self.client.delete(f'/api/authors/{self.author.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Author.objects.count(), 0)


class BookViewSetTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Author.objects.create(first_name="John", last_name="Doe")
        self.book = Book.objects.create(
            title="Test Book",
            author=self.author,
            isbn="1234567890123",
            genre="fiction",
            available_copies=5
        )
        self.user = User.objects.create_user(username='testuser', email='test@example.com')
        self.member = Member.objects.create(user=self.user)

    def test_list_books(self):
        response = self.client.get('/api/books/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_books_optimized(self):
        with self.assertNumQueries(2):
            response = self.client.get('/api/books/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_book(self):
        data = {
            'title': 'New Book',
            'author_id': self.author.id,
            'isbn': '9876543210987',
            'genre': 'sci-fi',
            'available_copies': 3
        }
        response = self.client.post('/api/books/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Book.objects.count(), 2)

    def test_retrieve_book(self):
        response = self.client.get(f'/api/books/{self.book.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Book')

    @patch('library.tasks.send_loan_notification.delay')
    def test_loan_book(self, mock_task):
        response = self.client.post(
            f'/api/books/{self.book.id}/loan/',
            {'member_id': self.member.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 4)
        self.assertEqual(Loan.objects.count(), 1)
        mock_task.assert_called_once()

    def test_loan_book_no_copies(self):
        self.book.available_copies = 0
        self.book.save()
        response = self.client.post(
            f'/api/books/{self.book.id}/loan/',
            {'member_id': self.member.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_loan_book_invalid_member(self):
        response = self.client.post(
            f'/api/books/{self.book.id}/loan/',
            {'member_id': 9999}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_return_book(self):
        loan = Loan.objects.create(book=self.book, member=self.member)
        self.book.available_copies = 4
        self.book.save()

        response = self.client.post(
            f'/api/books/{self.book.id}/return_book/',
            {'member_id': self.member.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 5)
        loan.refresh_from_db()
        self.assertTrue(loan.is_returned)

    def test_return_book_no_active_loan(self):
        response = self.client.post(
            f'/api/books/{self.book.id}/return_book/',
            {'member_id': self.member.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MemberViewSetTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', email='test@example.com')
        self.member = Member.objects.create(user=self.user)

    def test_list_members(self):
        response = self.client.get('/api/members/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_member(self):
        new_user = User.objects.create_user(username='newuser', email='new@example.com')
        data = {'user_id': new_user.id}
        response = self.client.post('/api/members/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_retrieve_member(self):
        response = self.client.get(f'/api/members/{self.member.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class LoanViewSetTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Author.objects.create(first_name="John", last_name="Doe")
        self.book = Book.objects.create(
            title="Test Book",
            author=self.author,
            isbn="1234567890123",
            genre="fiction",
            available_copies=5
        )
        self.user = User.objects.create_user(username='testuser', email='test@example.com')
        self.member = Member.objects.create(user=self.user)
        self.loan = Loan.objects.create(
            book=self.book,
            member=self.member
        )

    def test_list_loans(self):
        response = self.client.get('/api/loans/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_loan(self):
        response = self.client.get(f'/api/loans/{self.loan.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('due_date', response.data)

    def test_extend_due_date(self):
        original_due_date = self.loan.due_date
        response = self.client.post(
            f'/api/loans/{self.loan.id}/extend_due_date/',
            {'additional_days': 7}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.due_date, original_due_date + timedelta(days=7))

    def test_extend_due_date_invalid_days(self):
        response = self.client.post(
            f'/api/loans/{self.loan.id}/extend_due_date/',
            {'additional_days': -5}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_extend_overdue_loan(self):
        self.loan.due_date = timezone.now().date() - timedelta(days=5)
        self.loan.save()

        response = self.client.post(
            f'/api/loans/{self.loan.id}/extend_due_date/',
            {'additional_days': 7}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TopMemberViewTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Author.objects.create(first_name="John", last_name="Doe")
        self.book1 = Book.objects.create(
            title="Book 1", author=self.author, isbn="1111111111111", genre="fiction"
        )
        self.book2 = Book.objects.create(
            title="Book 2", author=self.author, isbn="2222222222222", genre="fiction"
        )
        self.book3 = Book.objects.create(
            title="Book 3", author=self.author, isbn="3333333333333", genre="fiction"
        )

        self.user1 = User.objects.create_user(username='user1', email='user1@example.com')
        self.member1 = Member.objects.create(user=self.user1)

        self.user2 = User.objects.create_user(username='user2', email='user2@example.com')
        self.member2 = Member.objects.create(user=self.user2)

        Loan.objects.create(book=self.book1, member=self.member1, is_returned=False)
        Loan.objects.create(book=self.book2, member=self.member1, is_returned=False)
        Loan.objects.create(book=self.book3, member=self.member2, is_returned=False)

    def test_top_active_members(self):
        response = self.client.get('/api/members/top-active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['username'], 'user1')
        self.assertEqual(response.data[0]['active_loans'], 2)
        self.assertEqual(response.data[1]['username'], 'user2')
        self.assertEqual(response.data[1]['active_loans'], 1)

    def test_top_active_members_excludes_returned(self):
        Loan.objects.filter(member=self.member1).update(is_returned=True)
        response = self.client.get('/api/members/top-active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'user2')


class CeleryTasksTestCase(TestCase):
    def setUp(self):
        self.author = Author.objects.create(first_name="John", last_name="Doe")
        self.book = Book.objects.create(
            title="Test Book",
            author=self.author,
            isbn="1234567890123",
            genre="fiction"
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='Test'
        )
        self.member = Member.objects.create(user=self.user)

    @patch('library.tasks.send_mail')
    def test_send_loan_notification(self, mock_send_mail):
        loan = Loan.objects.create(book=self.book, member=self.member)
        send_loan_notification(loan.id)

        mock_send_mail.assert_called_once()
        self.assertIn('Book Loaned Successfully', mock_send_mail.call_args[1]['subject'])
        self.assertIn(self.user.email, mock_send_mail.call_args[1]['recipient_list'])

    @patch('library.tasks.send_mail')
    def test_check_overdue_loans(self, mock_send_mail):
        loan = Loan.objects.create(
            book=self.book,
            member=self.member,
            due_date=timezone.now().date() - timedelta(days=5)
        )

        check_overdue_loans()

        mock_send_mail.assert_called_once()
        self.assertIn('Overdue', mock_send_mail.call_args[1]['subject'])
        self.assertIn(self.user.email, mock_send_mail.call_args[1]['recipient_list'])

    @patch('library.tasks.send_mail')
    def test_check_overdue_loans_no_overdue(self, mock_send_mail):
        loan = Loan.objects.create(
            book=self.book,
            member=self.member,
            due_date=timezone.now().date() + timedelta(days=5)
        )

        check_overdue_loans()

        mock_send_mail.assert_not_called()


class LoanModelTestCase(TestCase):
    def setUp(self):
        self.author = Author.objects.create(first_name="John", last_name="Doe")
        self.book = Book.objects.create(
            title="Test Book",
            author=self.author,
            isbn="1234567890123",
            genre="fiction"
        )
        self.user = User.objects.create_user(username='testuser')
        self.member = Member.objects.create(user=self.user)

    def test_due_date_auto_set(self):
        loan = Loan.objects.create(book=self.book, member=self.member)
        self.assertIsNotNone(loan.due_date)
        expected_due_date = loan.loan_date + timedelta(days=14)
        self.assertEqual(loan.due_date, expected_due_date)

    def test_custom_loan_duration(self):
        loan = Loan.objects.create(
            book=self.book,
            member=self.member,
            loan_duration=7
        )
        expected_due_date = loan.loan_date + timedelta(days=7)
        self.assertEqual(loan.due_date, expected_due_date)


class PaginationTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Author.objects.create(first_name="John", last_name="Doe")
        for i in range(30):
            Book.objects.create(
                title=f"Book {i}",
                author=self.author,
                isbn=f"123456789012{i}",
                genre="fiction"
            )

    def test_book_pagination(self):
        response = self.client.get('/api/books/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 25)
        self.assertIsNotNone(response.data['next'])

    def test_author_pagination(self):
        for i in range(30):
            Author.objects.create(first_name=f"Author{i}", last_name="Test")

        response = self.client.get('/api/authors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 25)
