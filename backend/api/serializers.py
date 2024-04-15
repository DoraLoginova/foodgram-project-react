import base64

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField
from rest_framework.validators import UniqueTogetherValidator

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


class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            'password',
        )


class CustomUserSerializer(UserSerializer):
    """Сериализатор пользователей с полем подписки."""

    is_subscribed = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name',
                  'email', 'is_subscribed')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        return request is not None and (
            request.user.is_authenticated and Subscribe.objects.filter(
                user=request.user, author=obj
            ).exists()
        )


class SubscribeUserSerializer(CustomUserSerializer):
    """Сериализатор списка подписок."""

    recipes_count = serializers.ReadOnlyField(source='recipes.count')
    recipes = SerializerMethodField()

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + (
            'recipes_count', 'recipes'
        )

    def get_recipes(self, obj):
        """Получение списка рецептов автора."""
        recipes = obj.recipes.all()
        if recipes:
            serializer = SubscribeRecipeSerializer(
                recipes,
                context={"request": self.context.get("request")},
                many=True,
            )
            return serializer.data
        return []

    def get_recipes_count(self, obj):
        return obj.recipes.count()


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


class Base64ImageField(serializers.ImageField):
    """Сериализатор поля image."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            img_format, img_str = data.split(';base64,')
            ext = img_format.split('/')[-1]
            data = ContentFile(base64.b64decode(img_str), name='temp.' + ext)
        return super().to_internal_value(data)


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор чтения рецепта."""

    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = IngredientInRecipeReadSerializer(
        many=True, read_only=True, source='ingredients_amounts'
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
        return request is not None and (
            request.user.is_authenticated and request.user.favorites.filter(
                recipe=obj
            ).exists()
        )

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        return request is not None and (
            request.user.is_authenticated
            and request.user.shopping_cart.filter(
                recipe=obj
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
        super().update(instance, validated_data)
        instance.tags.set(tags_data)
        instance.ingredients.clear()
        self._add_ingredients(ingredients_data, instance)
        return instance

    def to_representation(self, instance):
        return RecipeReadSerializer(instance, context=self.context).data


class SubscribeRecipeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FavoriteSerializer(SubscribeRecipeSerializer):
    """Сериализатор для получения/добавления/удаления из/в избранного."""

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
    )
    recipe = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(),
        write_only=True,
    )

    class Meta:
        model = FavoriteRecipe
        fields = ('user', 'recipe',)

    def validate(self, data):
        request = self.context['request']
        user = data['user']
        recipe = data['recipe']
        favorites = recipe.favorites.filter(user=user)
        if request.method == 'POST':
            if favorites.exists():
                raise ValidationError('Рецепт уже есть в избранном.')
        if request.method == 'DELETE':
            if not favorites.exists():
                raise ValidationError('Рецепт не найден в избранном.')
        return data


class ShoppingCartSerializer(SubscribeRecipeSerializer):
    """Сериализатор для получения/добавления/удаления из списка покупок."""

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
    )
    recipe = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(),
        write_only=True,
    )

    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe',)

    def validate(self, data):
        request = self.context['request']
        user = data['user']
        recipe = data['recipe']
        shopping_cart = recipe.shopping_cart.filter(user=user)
        if request.method == 'POST':
            if shopping_cart.exists():
                raise ValidationError('Рецепт уже есть в списке покупок.')
        if request.method == 'DELETE':
            if not shopping_cart.exists():
                raise ValidationError('Рецепта нет в списке покупок.')
        return data
