from django.contrib.auth.models import AbstractUser
from django.core import validators
from django.db import models


class User(AbstractUser):
    email = models.EmailField('Адрес электронной почты',
                              unique=True, max_length=254)
    username = models.CharField('Уникальный юзернейм',
                                unique=True, max_length=150,
                                validators=[
                                    validators.RegexValidator(
                                        r'^[\w.@+-]+\Z',
                                        'Введите правильный юзернейм.')])
    first_name = models.CharField('Имя', max_length=150)
    last_name = models.CharField('Фамилия', max_length=150)
    password = models.CharField('Пароль', max_length=150)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('id',)

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
