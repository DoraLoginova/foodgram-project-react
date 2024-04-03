from django.db import models

from users.models import User


class Ingredient(models.Model):
    """ Модель Ингридиент."""

    name = models.CharField('Название ингредиента', max_length=200)
    measurement_unit = models.CharField('Единица измерения', max_length=200)

    class Meta:
        ordering = ('name',)
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}.'


class Tag(models.Model):
    """ Модель Тэг. """

    name = models.CharField('Имя', max_length=60, unique=True)
    color = models.CharField('Цвет', max_length=7, unique=True)
    slug = models.SlugField('Ссылка', max_length=100, unique=True)

    class Meta:
        verbose_name = 'Тэг'
        verbose_name_plural = 'Тэги'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='recipe',
                               verbose_name='Автор')
    name = models.CharField('Название рецепта', max_length=255)
    image = models.ImageField('Изображение рецепта',
                              upload_to='static/recipe/',
                              blank=True, null=True)
    text = models.TextField('Описание рецепта')
    ingredients = models.ManyToManyField(Ingredient,
                                         through='RecipeIngredient',
                                         related_name='recipes',
                                         verbose_name='Ингредиенты')
    tags = models.ManyToManyField(Tag, verbose_name='Тэги',
                                  related_name='recipes')
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name='Время приготовления в минутах',)
# validators=[validators.MinValueValidator(
# 1, message='Мин. время приготовления 1 минута'), ])
    pub_date = models.DateTimeField('Дата публикации', auto_now_add=True)

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ('-pub_date', )

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    """Сериализатор для связи Recipe и Ingredient."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               related_name='recipe', verbose_name='Рецепт')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE,
                                   related_name='ingredient',
                                   verbose_name='Ингредиент')
    amount = models.PositiveSmallIntegerField(
        'Количество', )
# validators=(validators.MinValueValidator(1,
# message='Мин. количество ингридиентов 1')))

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Количество ингредиентов'
        ordering = ('-id',)


class FavoriteRecipe(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='favorites',
                               verbose_name='Пользователь')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               related_name='favorites',
                               verbose_name='Избранный рецепт')

    class Meta:
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        ordering = ('recipe',)

    def __str__(self):
        return f'{self.author} добавил {self.recipe} в избранные.'


class ShoppingCart(models.Model):
    author = models.OneToOneField(User, on_delete=models.CASCADE,
                                  related_name='shopping_cart',
                                  verbose_name='Пользователь')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               related_name='shopping_cart',
                               verbose_name='Покупка')

    class Meta:
        verbose_name = 'Рецепт в списке покупок'
        verbose_name_plural = 'Рецепты в списке покупок'
        ordering = ('recipe',)

    def __str__(self):
        return f'{self.author} добавил {self.recipe} в покупки.'
