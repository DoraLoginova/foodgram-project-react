import base64
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers, status
from rest_framework.relations import SlugRelatedField
from rest_framework.validators import ValidationError
from rest_framework.fields import IntegerField, SerializerMethodField

from recipes.models import (Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag, FavoriteRecipe)
from users.models import Subscribe, User


class Base64ImageField(serializers.ImageField):
    """Сериализатор обработки изображений в формате base64."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)

        return super().to_internal_value(data)


class CustomUserSerializer(UserSerializer):
    """Сериализатор юзера с дополнительным полем is_subscribed."""

    is_subscribed = serializers.SerializerMethodField(read_only=True)

    def get_is_subscribed(self, obj):
        """Определение поля is_subscribed."""

        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Subscribe.objects.filter(user=user, author=obj).exists()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name',
                  'last_name', 'is_subscribed',)


class CreateUserSerializer(UserCreateSerializer):
    """Сериализатор создания пользователей."""

    def validate_username(self, value):
        """Запрет на использование имени 'me'."""
        if value.lower() == 'me':
            raise serializers.ValidationError(
                detail='Имя "me" не валидно',
                code=status.HTTP_400_BAD_REQUEST
            )
        return value

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name',
                  'last_name', 'password',)
        read_only_fields = ('id',)


class SubscribeSerializer(serializers.ModelSerializer):
    """Сериализатор подписок."""

    user = SlugRelatedField(
        queryset=User.objects.all(),
        slug_field='username',
        default=serializers.CurrentUserDefault(),
    )
    author = SlugRelatedField(
        queryset=User.objects.all(), slug_field='username')

    def validate(self, data):
        if data['user'] == data['author']:
            raise ValidationError(
                detail='Вы не можете подписаться на самого себя!',
                code=status.HTTP_400_BAD_REQUEST
            )
        return data

    class Meta:
        model = Subscribe
        fields = ('id', 'user', 'author',)


class SubscribeUserSerializer(CustomUserSerializer):
    """Сериализатор для модели Subscribe."""

    recipes_count = SerializerMethodField()
    recipes = SerializerMethodField()

    def get_recipes_count(self, user):
        """Получение количества рецептов."""

        return user.recipes.count()

    def get_recipes(self, user):
        """Получение рецептов."""

        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = user.recipes.all()
        if limit:
            recipes = recipes[:int(limit)]
        serializer = RecipeLittleSerializer(recipes, many=True, read_only=True)
        return serializer.data

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + (
            'recipes_count', 'recipes'
        )


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Ingredient."""

    class Meta:
        model = Ingredient
        fields = '__all__'


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Tag."""

    class Meta:
        model = Tag
        fields = '__all__'


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Recipe - чтение данных."""

    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = SerializerMethodField()
    image = Base64ImageField()
    is_favorited = SerializerMethodField(read_only=True)
    is_in_shopping_cart = SerializerMethodField(read_only=True)

    def get_ingredients(self, obj):
        """Получение ингредиентов."""

        recipe = obj
        ingredients = recipe.ingredients.values(
            'id', 'name', 'measurement_unit',
            amount=F('recipeingredient__amount')
        )
        return ingredients

    def get_is_favorited(self, obj):
        """Находится ли рецепт в избранных."""

        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return FavoriteRecipe.objects.filter(recipe=obj, author=user).exists()

    def get_is_in_shopping_cart(self, obj):
        """Находится ли рецепт в корзине текущего пользователя."""

        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return ShoppingCart.objects.filter(recipe=obj, author=user).exists

    class Meta:
        model = Recipe
        fields = ('id', 'author', 'name', 'image', 'text', 'ingredients',
                  'tags', 'cooking_time', 'is_favorited',
                  'is_in_shopping_cart',)


class IngredientInRecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для ingredients модели Recipe."""

    id = IntegerField(write_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount',)


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Recipe."""

    ingredients = IngredientInRecipeWriteSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True)

    def validate_ingredients(self, ingredients):
        """Проверка ингредиентов."""

        if not ingredients:
            raise ValidationError({
                    'ingredients': 'Нужен хотя бы один ингредиент!'
                })
        for item in ingredients:
            if int(item['amount']) < 1:
                raise serializers.ValidationError({
                    'amount': 'Минимальное количество ингредиентов - 1.'
                })
        return ingredients

    def validate_tags(self, tags):
        """Проверка тегов."""

        if not tags:
            raise serializers.ValidationError({
                'tags': 'У рецепта должен быть минимум 1 тег.'
            })
        tags_list = []
        for tag in tags:
            if tag in tags_list:
                raise ValidationError({'tags': 'Теги не должны повторяться!'})
            tags_list.append(tag)
        return tags

    @transaction.atomic
    def add_ingredients_amount(self, ingredients, recipe):
        """Добавляет ингридиенты."""

        RecipeIngredient.objects.bulk_create(
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient.get('id'),
                amount=ingredient.get('amount'),
            )
            for ingredient in ingredients
        )

    @transaction.atomic
    def create(self, validated_data):
        """Создаёт рецепт."""

        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)
        self.add_ingredients_amount(ingredients_data, recipe)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновляет рецепт."""

        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredients')
        instance = super().update(instance, validated_data)
        instance.tags.clear()
        instance.tags.set(tags_data)
        instance.ingredients.clear()
        self.add_ingredients_amount(ingredients_data, instance)
        instance.save()
        return instance

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return RecipeReadSerializer(instance, context=context).data

    class Meta:
        model = Recipe
        fields = ('ingredients', 'tags', 'image', 'name', 'text',
                  'cooking_time', 'author',)


class RecipeLittleSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода рецептов в SubscribeUserSerializer."""

    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для FavoriteRecipe."""

    def validate(self, data):
        request = self.context['request']
        author = data['author']
        recipe = data['recipe']
        favorites = recipe.favorites.filter(author=author)
        if request.method == 'POST':
            if favorites.exists():
                raise ValidationError({'recipe': 'Рецепт уже в избранном.'})
        if request.method == 'DELETE':
            if not favorites.exists():
                raise ValidationError({'recipe': 'Рецепт не найден.'})
        return data

    class Meta:
        model = FavoriteRecipe
        fields = ('author', 'recipe',)


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для ShoppingCart."""

    def validate(self, data):
        request = self.context['request']
        author = data['author']
        recipe = data['recipe']
        shopping_cart = recipe.shopping_cart.filter(author=author)
        if request.method == 'POST':
            if shopping_cart.exists():
                raise ValidationError({
                    'recipe': 'Рецепт уже в списке покупок.'
                })
        if request.method == 'DELETE':
            if not shopping_cart.exists():
                raise ValidationError({
                    'recipe': 'Рецепта нет в списке покупок.'
                })
        return data

    class Meta:
        model = ShoppingCart
        fields = ('author', 'recipe',)
