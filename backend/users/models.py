from django.contrib.auth.models import AbstractUser
from django.core import validators
from django.db import models

from users.constants import (
    MAX_EMAIL_LENGTH,
    MAX_NAME_LENGTH,
)


class User(AbstractUser):
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [
        'username',
        'first_name',
        'last_name',
    ]
    email = models.EmailField(
        'email address',
        max_length=MAX_EMAIL_LENGTH,
        unique=True,
    )
    username = models.CharField(
        max_length=MAX_NAME_LENGTH,
        unique=True,
        validators=[
            validators.RegexValidator(
                r'^[\w.@+-]+\Z', 'Введите правильный юзернейм.', 'invalid'
            ),
        ],
        verbose_name='Уникальный юзернейм',
    )
    first_name = models.CharField(max_length=MAX_NAME_LENGTH,)
    last_name = models.CharField(max_length=MAX_NAME_LENGTH,)
    password = models.CharField(max_length=MAX_NAME_LENGTH,)

    class Meta:
        ordering = ('username',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Subscribe(models.Model):
    user = models.ForeignKey(
        User,
        related_name='subscriber',
        verbose_name="Подписчик",
        on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        User,
        related_name='subscribing',
        verbose_name="Автор",
        on_delete=models.CASCADE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'author'],
                name='unique_subscription'
            ),
            models.CheckConstraint(
                check=~models.Q(user=models.F('author')),
                name='user_cannot_follow_himself',
            )]
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
