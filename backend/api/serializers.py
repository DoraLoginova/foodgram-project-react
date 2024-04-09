from django.contrib.auth import authenticate, get_user_model
from django.db.models import F
import django.contrib.auth.password_validation as validators
from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404
from djoser.serializers import UserCreateSerializer, UserSerializer
from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers
from rest_framework import status

from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag
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


class CustomUserListSerializer(UserSerializer):
    """Сериализатор списка пользователей с полем подписки."""

    is_subscribed = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name',
                  'is_subscribed')

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Subscribe.objects.filter(user=user, author=obj).exists()


class PasswordSerializer(serializers.Serializer):
    """Сериализатор паролей."""

    new_password = serializers.CharField(label='Новый пароль')
    current_password = serializers.CharField(label='Текущий пароль')

    def validate_current_password(self, current_password):
        user = self.context['request'].user
        if not authenticate(username=user.email,
                            password=current_password):
            raise serializers.ValidationError(
                'Не удается войти с предоставленными учетными данными.')
        return current_password

    def validate_new_password(self, new_password):
        validators.validate_password(new_password)
        return new_password

    def create(self, validated_data):
        user = self.context['request'].user
        password = make_password(validated_data.get('new_password'))
        user.password = password
        user.save()
        return validated_data


class SubscribeSerializer(CustomUserListSerializer):
    """Сериализатор подписок."""

    recipes_count = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()

    class Meta(CustomUserListSerializer.Meta):
        fields = CustomUserListSerializer.Meta.fields + (
            'recipes_count', 'recipes'
        )
        read_only_fields = ('email', 'username')

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[:int(limit)]
        serializer = SubscribeRecipeSerializer(recipes, many=True,
                                               read_only=True)
        return serializer.data

    def validate(self, data):
        author = self.instance
        user = self.context.get('request').user
        if Subscribe.objects.filter(author=author, user=user).exists():
            raise validators.ValidationError(
                detail='Вы уже подписаны на этого пользователя!',
                code=status.HTTP_400_BAD_REQUEST
            )
        if user == author:
            raise validators.ValidationError(
                detail='На самого себя не подписаться!',
                code=status.HTTP_400_BAD_REQUEST
            )
        return data


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов в рецепте."""

    id = serializers.IntegerField(write_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор создания рецепта."""

    image = Base64ImageField()
    tags = serializers.PrimaryKeyRelatedField(many=True,
                                              queryset=Tag.objects.all())
    ingredients = RecipeIngredientSerializer(many=True)

    class Meta:
        model = Recipe
        fields = '__all__'
        read_only_fields = ('author',)

    def validate(self, data):
        ingredients = data['ingredients']
        ingredient_list = []
        for items in ingredients:
            ingredient = get_object_or_404(
                Ingredient, id=items['id'])
            if ingredient in ingredient_list:
                raise serializers.ValidationError(
                    'Ингредиент должен быть уникальным!')
            ingredient_list.append(ingredient)
        tags = data['tags']
        if not tags:
            raise serializers.ValidationError(
                'Нужен хотя бы один тэг для рецепта!')
        for tag_name in tags:
            if not Tag.objects.filter(name=tag_name).exists():
                raise serializers.ValidationError(
                    f'Тэга {tag_name} не существует!')
        return data

    def validate_cooking_time(self, cooking_time):
        if int(cooking_time) < 1:
            raise serializers.ValidationError(
                'Время приготовления >= 1!')
        return cooking_time

    def validate_ingredients(self, ingredients):
        if not ingredients:
            raise serializers.ValidationError(
                'Мин. 1 ингредиент в рецепте!')
        for ingredient in ingredients:
            if int(ingredient.get('amount')) < 1:
                raise serializers.ValidationError(
                    'Количество ингредиента >= 1!')
        return ingredients

    def create_ingredients(self, ingredients, recipe):
        for ingredient in ingredients:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient_id=ingredient.get('id'),
                amount=ingredient.get('amount'), )

    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags)
        self.create_ingredients(ingredients, recipe)
        return recipe

    def update(self, instance, validated_data):
        if 'ingredients' in validated_data:
            ingredients = validated_data.pop('ingredients')
            instance.ingredients.clear()
            self.create_ingredients(ingredients, instance)
        if 'tags' in validated_data:
            instance.tags.set(
                validated_data.pop('tags'))
        return super().update(
            instance, validated_data)

    def to_representation(self, instance):
        return RecipeReadSerializer(
            instance,
            context={'request': self.context.get('request')}).data


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор чтения рецепта."""

    image = Base64ImageField()
    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserListSerializer(read_only=True,
                                      default=serializers.CurrentUserDefault())
    ingredients = serializers.SerializerMethodField()
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = '__all__'

    def get_ingredients(self, obj):
        recipe = obj
        ingredients = recipe.ingredients.values(
            'id', 'name', 'measurement_unit',
            amount=F('recipeingredient__amount'))
        return ingredients

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return user.favorites.filter(recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return user.shopping_cart.filter(recipe=obj).exists()


class SubscribeRecipeSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
