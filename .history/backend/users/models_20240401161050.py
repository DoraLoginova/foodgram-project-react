from django.contrib.auth.models import AbstractUser
from django.core import validators
from django.db import models


class User(AbstractUser):
    email = models.EmailField('Email', max_length=200, unique=True,)
    first_name = models.CharField('Имя', max_length=150)
    last_name = models.CharField('Фамилия', max_length=150)
    username = models.CharField(unique=True, max_length=150,
                                validators=[validators.RegexValidator(
                                             r'^[\w.@+-]+\Z', 
                                            'Введите правильный юзернейм.'),],
                                verbose_name='Уникальный юзернейм',)
    password = models.CharField('Пароль', max_length=150)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('id',)

    def __str__(self):
        return self.username


class Subscribe(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='subscriber',
                             verbose_name='Подписчик',)
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='subscribing',
                               verbose_name='Автор',)
    created = models.DateTimeField('Дата подписки', auto_now_add=True)

    class Meta:
        ordering = ['-id']
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'author'], name='unique_subscription'
            ),
        ]
