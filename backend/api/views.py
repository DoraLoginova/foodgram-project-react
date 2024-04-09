from datetime import datetime

from django.db.models import Sum
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet
from django_filters.rest_framework import DjangoFilterBackend
from recipes.models import (FavoriteRecipe, Ingredient,
                            Recipe, RecipeIngredient,
                            ShoppingCart, Tag)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .filters import IngredientFilter, RecipeFilter
from .pagination import LimitPageNumberPagination
from .permissions import IsAdminOrReadOnly, IsAuthorOrReadOnly
from .serializers import (IngredientSerializer, CustomUserListSerializer,
                          RecipeReadSerializer, RecipeWriteSerializer,
                          SubscribeSerializer, SubscribeRecipeSerializer,
                          TagSerializer)
from users.models import Subscribe

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    """Вьюсет пользователей."""

    queryset = User.objects.all()
    serializer_class = CustomUserListSerializer
    pagination_class = LimitPageNumberPagination

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def subscribe(self, request, **kwargs):
        user = request.user
        author_id = self.kwargs.get('id')
        author = get_object_or_404(User, id=author_id)

        if request.method == 'POST':
            serializer = SubscribeSerializer(author,
                                             data=request.data,
                                             context={"request": request})
            serializer.is_valid(raise_exception=True)
            Subscribe.objects.create(user=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            subscription = get_object_or_404(Subscribe, user=user,
                                             author=author)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        """Получить на кого пользователь подписан."""
        user = request.user
        queryset = User.objects.filter(subscribing__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = SubscribeSerializer(pages, many=True,
                                         context={'request': request})
        return self.get_paginated_response(serializer.data)


class IngredientViewSet(ReadOnlyModelViewSet):
    """Ингредиенты."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter


class TagViewSet(ReadOnlyModelViewSet):
    """Тэги."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (IsAdminOrReadOnly,)


class RecipeViewSet(ModelViewSet):
    """Рецепты."""

    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly or IsAdminOrReadOnly,)
    pagination_class = LimitPageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk):
        """Добавление и удаление рецепта в/из избранных."""
        if request.method == 'POST':
            return self.addition(FavoriteRecipe, request.user, pk)
        else:
            return self.deletion(FavoriteRecipe, request.user, pk)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk):
        """Добавление и удаление рецепта в/из корзины."""
        if request.method == 'POST':
            return self.addition(ShoppingCart, request.user, pk)
        else:
            return self.deletion(ShoppingCart, request.user, pk)

    def addition(self, model, user, pk):
        if model.objects.filter(user=user, recipe__id=pk).exists():
            return Response({'errors': 'Рецепт уже добавлен!'},
                            status=status.HTTP_400_BAD_REQUEST)
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = SubscribeRecipeSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def deletion(self, model, user, pk):
        obj = model.objects.filter(user=user, recipe__id=pk)
        if obj.exists():
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'errors': 'Рецепт уже удален!'},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        """Качаем список покупок с ингредиентами."""
        user = request.user
        if not user.shopping_cart.exists():
            return Response(status=status.HTTP_400_BAD_REQUEST)

        ingredients = RecipeIngredient.objects.filter(
            recipe__shopping_cart__user=request.user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(amount=Sum('amount'))

        today = datetime.today()
        shopping_list = (
            f'Список покупок для: {user.get_full_name()}\n\n'
            f'Дата: {today:%Y-%m-%d}\n\n'
        )
        shopping_list += '\n'.join([
            f'- {ingredient["ingredient__name"]} '
            f'({ingredient["ingredient__measurement_unit"]})'
            f' - {ingredient["amount"]}'
            for ingredient in ingredients
        ])
        shopping_list += f'\n\nFoodgram ({today:%Y})'

        filename = f'{user.username}_shopping_list.txt'
        response = HttpResponse(shopping_list, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={filename}'

        return response
