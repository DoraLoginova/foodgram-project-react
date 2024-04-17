from django.contrib.auth import get_user_model
from django.core import validators
from django.db import models
from django.db.models import UniqueConstraint

from recipes.constants import (
    MAX_COOKING_TIME,
    MAX_COLOR_TAG,
    MIN_COOKING_TIME,
    MAX_INGREDIENT_AMOUNT,
    MAX_INGREDIENT_LENGTH,
    MIN_INGREDIENT_AMOUNT,
    MAX_RECIPE_LENGTH,
    MAX_TAG_LENGTH,
)

User = get_user_model()


class Tag(models.Model):
    """Модель Тэг."""

    name = models.CharField('Имя', max_length=MAX_TAG_LENGTH, unique=True,)
    color = models.CharField(
        'Цвет',
        max_length=MAX_COLOR_TAG,
        validators=[
            validators.RegexValidator(
                regex='^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$',
                message='Введенное значение не является цветом в формате HEX!'
            )
        ],
        unique=True,
    )
    slug = models.SlugField('Ссылка', max_length=MAX_TAG_LENGTH, unique=True,)

    class Meta:
        verbose_name = 'Тэг'
        verbose_name_plural = 'Тэги'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """Модель Ингридиент."""

    name = models.CharField(
        'Название ингредиента',
        max_length=MAX_INGREDIENT_LENGTH,
    )
    measurement_unit = models.CharField(
        'Единица измерения ингредиента',
        max_length=MAX_INGREDIENT_LENGTH,
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ('name',)
        constraints = (
            models.UniqueConstraint(
                fields=('name', 'measurement_unit'),
                name='unique_ingredient',
            ),
        )

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}.'


class Recipe(models.Model):
    """Модель Рецепт."""

    author = models.ForeignKey(
        User,
        related_name='recipes',
        on_delete=models.CASCADE,
        verbose_name='Автор',
    )
    name = models.CharField(
        'Название рецепта',
        max_length=MAX_RECIPE_LENGTH,
    )
    image = models.ImageField(
        'Изображение',
        upload_to='recipes/',
        blank=True,
        null=True,
    )
    text = models.TextField('Описание рецепта')
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',
        related_name='recipes',
        verbose_name='Ингредиенты',
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Тэги',
        related_name='recipes',
    )
    cooking_time = models.PositiveSmallIntegerField(
        'Время приготовления',
        validators=[
            validators.MinValueValidator(
                MIN_COOKING_TIME,
                message=f'Мин. время {MIN_COOKING_TIME} минута'
            ),
            validators.MaxValueValidator(
                MAX_COOKING_TIME,
                message=f'Максим. время {MAX_COOKING_TIME} минут'
            ),
        ],
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ('name', )

    def __str__(self):
        return f'{self.name}'


class RecipeIngredient(models.Model):
    """Модель для связи Ингридиента и Рецепта."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='ingredients_amounts',
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент',
    )
    amount = models.PositiveSmallIntegerField(
        'Количество',
        validators=(
            validators.MinValueValidator(
                MIN_INGREDIENT_AMOUNT,
                message=f'Мин. количество ингридиентов {MIN_INGREDIENT_AMOUNT}'
            ),
            validators.MaxValueValidator(
                MAX_INGREDIENT_AMOUNT,
                message=f'Максим. количество {MAX_INGREDIENT_AMOUNT}'
            ),
        ),
    )

    class Meta:
        verbose_name = 'Количество ингредиента'
        verbose_name_plural = 'Количество ингредиентов'
        ordering = ('recipe',)
        constraints = (
            models.UniqueConstraint(
                fields=('recipe', 'ingredient'),
                name='unique_ingredient_in_recipe',
            ),
        )


class RecipeUserModel(models.Model):
    """Абстрактная модель. Определяет поля recipe и user."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )

    class Meta:
        abstract = True


class FavoriteRecipe(RecipeUserModel):
    """Модель Избранный рецепт."""

    class Meta:
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        default_related_name = 'favorites'
        constraints = [
            UniqueConstraint(fields=['user', 'recipe'],
                             name='unique_favourite')
        ]

    def __str__(self):
        return f'Пользователь {self.user} добавил {self.recipe} в избранные.'


class ShoppingCart(RecipeUserModel):
    """Модель Корзина покупок."""

    class Meta:
        verbose_name = 'Покупка'
        verbose_name_plural = 'Покупки'
        default_related_name = 'shopping_cart'
        constraints = [
            UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_shopping_cart',
            )
        ]

    def __str__(self):
        return f'Пользователь {self.user} добавил {self.recipe} в покупки.'
