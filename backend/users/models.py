from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core import validators


class User(AbstractUser):
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [
        'id',
        'username',
        'first_name',
        'last_name',
    ]
    email = models.EmailField('email address', max_length=254,
                              unique=True,)
    username = models.CharField(
        max_length=150, unique=True,
        validators=[
            validators.RegexValidator(
                r'^[\w.@+-]+\Z', 'Введите правильный юзернейм.', 'invalid'
            ),
        ],
        verbose_name='Уникальный юзернейм',)
    first_name = models.CharField(max_length=150,)
    last_name = models.CharField(max_length=150,)
    password = models.CharField(max_length=150,)

    class Meta:
        ordering = ('id',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Subscribe(models.Model):
    user = models.ForeignKey(User, related_name='subscriber',
                             verbose_name="Подписчик",
                             on_delete=models.CASCADE)
    author = models.ForeignKey(User, related_name='subscribing',
                               verbose_name="Автор",
                               on_delete=models.CASCADE)

    class Meta:
        ordering = ('-id',)
        constraints = [
            models.UniqueConstraint(fields=['user', 'author'],
                                    name='unique_subscription')]
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
