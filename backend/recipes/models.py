from django.core import validators
from django.db import models
from django.db.models import UniqueConstraint

from users.models import User


class Tag(models.Model):
    """Модель Тэг."""

    name = models.CharField('Имя', max_length=200, unique=True)
    color = models.CharField(
        'Цвет', max_length=7, validators=[
            validators.RegexValidator(
                regex='^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$',
                message='Введенное значение не является цветом в формате HEX!'
            )
        ], unique=True)
    slug = models.SlugField('Ссылка', max_length=200, unique=True)

    class Meta:
        verbose_name = 'Тэг'
        verbose_name_plural = 'Тэги'
        ordering = ('-id',)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """Модель Ингридиент."""

    name = models.CharField('Название ингредиента', max_length=200)
    measurement_unit = models.CharField('Единица измерения ингредиента',
                                        max_length=200)

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ('name',)

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}.'


class Recipe(models.Model):
    """Модель Рецепт."""

    author = models.ForeignKey(User, related_name='recipes',
                               on_delete=models.SET_NULL,
                               null=True,
                               verbose_name='Автор')
    name = models.CharField('Название рецепта', max_length=200)
    image = models.ImageField('Изображение', upload_to='recipes/',
                              blank=True, null=True)
    text = models.TextField('Описание рецепта')
    ingredients = models.ManyToManyField(Ingredient,
                                         through='RecipeIngredient',
                                         related_name='recipes',
                                         verbose_name='Ингредиенты')
    tags = models.ManyToManyField(Tag, verbose_name='Тэги',
                                  related_name='recipes')
    cooking_time = models.PositiveSmallIntegerField(
        'Время приготовления',
        validators=[validators.MinValueValidator(
            1, message='Мин. время приготовления 1 минута'), ])

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ('-id', )

    def __str__(self):
        return f'{self.name}'


class RecipeIngredient(models.Model):
    """Модель для связи Ингридиента и Рецепта."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               related_name='ingredient_list',
                               verbose_name='Рецепт')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE,
                                   verbose_name='Ингредиент')
    amount = models.PositiveSmallIntegerField(
        'Количество',
        validators=(validators.MinValueValidator(
            1, message='Мин. количество ингридиентов 1'),))

    class Meta:
        verbose_name = 'Количество ингредиента'
        verbose_name_plural = 'Количество ингредиентов'
        ordering = ('-id',)


class FavoriteRecipe(models.Model):
    """Модель Избранный рецепт."""

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='favorites',
                             verbose_name='Пользователь')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               related_name='favorites',
                               verbose_name='Избранный рецепт')

    class Meta:
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        constraints = [
            UniqueConstraint(fields=['user', 'recipe'],
                             name='unique_favourite')
        ]

    def __str__(self):
        return f'Пользователь {self.user} добавил {self.recipe} в избранные.'


class ShoppingCart(models.Model):
    """Модель Корзина покупок."""

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='shopping_cart',
                             verbose_name='Пользователь')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               related_name='shopping_cart',
                               verbose_name='Покупка')

    class Meta:
        verbose_name = 'Покупка'
        verbose_name_plural = 'Покупки'
        constraints = [
            UniqueConstraint(fields=['user', 'recipe'],
                             name='unique_shopping_cart')
        ]

    def __str__(self):
        return f'Пользователь {self.user} добавил {self.recipe} в покупки.'
