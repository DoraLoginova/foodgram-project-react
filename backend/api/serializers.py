from django.contrib.auth import get_user_model
from django.db import transaction
from djoser.serializers import UserSerializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField
from rest_framework.validators import UniqueTogetherValidator

from api.fields import Base64ImageField
from foodgram.settings import RECIPES_LIMIT
from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
    FavoriteRecipe
)
from users.models import Subscribe

User = get_user_model()


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор тегов."""

    class Meta:
        model = Tag
        fields = '__all__'


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов."""

    class Meta:
        model = Ingredient
        fields = '__all__'


class CustomUserSerializer(UserSerializer):
    """Сериализатор пользователей с полем подписки."""

    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email',
                  'is_subscribed')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        return (request and request.user.is_authenticated
                and Subscribe.objects.filter(
                    user=request.user, author=obj).exists())


class SubscribeUserSerializer(CustomUserSerializer):
    """Сериализатор списка подписок."""

    recipes_count = serializers.ReadOnlyField(source='recipes.count')
    recipes = SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email',
            'is_subscribed', 'recipes', 'recipes_count'
        )

    def get_recipes(self, obj):
        """Получение списка рецептов."""
        recipes = obj.recipes.all()[:RECIPES_LIMIT]
        return SubscribeRecipeSerializer(recipes, many=True).data


class SubscribeSerializer(serializers.ModelSerializer):
    """Сериализатор подписки."""

    class Meta:
        model = Subscribe
        fields = ('user', 'author',)
        validators = [
            UniqueTogetherValidator(
                queryset=Subscribe.objects.all(),
                fields=('user', 'author'),
                message='Вы уже подписаны на этого пользователя!'
            )
        ]

    def validate(self, data):
        user = data.get('user')
        author = data.get('author')
        if user == author:
            raise ValidationError(
                {'errors': 'На самого себя не подписаться!'},
                code=status.HTTP_400_BAD_REQUEST
            )
        return data


class IngredientInRecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для связаной модели Recipe и Ingredient."""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class IngredientInRecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для поля ingredients -создание ингредиентов."""

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())

    class Meta:
        model = RecipeIngredient
        fields = (
            'id',
            'amount',
        )


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор чтения рецепта."""

    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = IngredientInRecipeReadSerializer(
        many=True, source='ingredients_amounts'
    )
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time'
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        return (
            request and request.user.is_authenticated
            and request.user.favorites.filter(
                user=request.user, recipe=obj
            ).exists()
        )

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        return (
            request and request.user.is_authenticated
            and request.user.shopping_cart.filter(
                user=request.user, recipe=obj
            ).exists()
        )


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор создания рецепта."""

    ingredients = IngredientInRecipeWriteSerializer(
        source='ingredients_amounts', many=True
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True)

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'name',
                  'image', 'text', 'cooking_time')

    def validate(self, obj):
        self.validate_tags(obj.get('tags'))
        self.validate_ingredients(obj.get('ingredients_amounts'))
        return obj

    def validate_tags(self, value):
        tags = value
        if not tags:
            raise serializers.ValidationError(
                {'tags': 'Нужно выбрать хотя бы один тег!'}
            )
        tags_list = []
        for tag in tags:
            tags_list.append(tag)
        if len(tags_list) > len(set(tags_list)):
            raise serializers.ValidationError(
                {'error': 'Тэги должны быть уникальны!'}
            )
        return value

    def validate_ingredients(self, value):
        ingredients = value
        if not ingredients:
            raise serializers.ValidationError(
                {'ingredients': 'Нужен хотя бы один ингредиент!'}
            )
        ingredients_list = []
        for ingredient in ingredients:
            ingredients_list.append(ingredient['id'])
        if len(ingredients_list) > len(set(ingredients_list)):
            raise serializers.ValidationError(
                {'error': 'Ингредиенты должны быть уникальны!'}
            )
        return value

    @staticmethod
    def _add_ingredients(ingredients_data, recipe):
        """Добавляет ингридиенты."""
        RecipeIngredient.objects.bulk_create(
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient.get('id'),
                amount=ingredient.get('amount'),
            )
            for ingredient in ingredients_data
        )

    @transaction.atomic
    def create(self, validated_data):
        """Создаёт рецепт."""
        author = self.context.get('request').user
        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredients_amounts')
        recipe = Recipe.objects.create(**validated_data, author=author)
        recipe.tags.set(tags_data)
        self._add_ingredients(ingredients_data, recipe)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновляет рецепт."""
        ingredients_data = validated_data.pop('ingredients_amounts')
        tags_data = validated_data.pop('tags')
        instance.tags.set(tags_data)
        instance.ingredients.clear()
        self._add_ingredients(ingredients_data, instance)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        return RecipeReadSerializer(instance, context=self.context).data


class SubscribeRecipeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FavoriteSerializer(SubscribeRecipeSerializer):
    """Сериализатор для получения/добавления/удаления из/в избранного."""

    class Meta:
        model = FavoriteRecipe
        fields = ('user', 'recipe',)
        validators = [
            UniqueTogetherValidator(
                queryset=FavoriteRecipe.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже есть в избранном.'
            )
        ]

    def to_representation(self, instance):
        return SubscribeRecipeSerializer(
            instance.recipe, context=self.context
        ).data


class ShoppingCartSerializer(SubscribeRecipeSerializer):
    """Сериализатор для получения/добавления/удаления из списка покупок."""

    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe',)
        validators = [
            UniqueTogetherValidator(
                queryset=ShoppingCart.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже есть в списке покупок.'
            )
        ]

    def to_representation(self, instance):
        return SubscribeRecipeSerializer(
            instance.recipe, context=self.context
        ).data
