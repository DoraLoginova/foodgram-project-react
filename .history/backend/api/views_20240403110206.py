from datetime import datetime
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser import views as djoser_views
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    SAFE_METHODS, IsAuthenticated, IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response

from api.pagination import LimitPageNumberPagination
from api.permissions import IsAdminOrReadOnly
from recipes.models import (Ingredient, Recipe,
                            RecipeIngredient, Tag,)
from users.models import User, Subscribe

from .filters import IngredientFilter, RecipeFilter
from .serializers import (CustomUserSerializer, FavoriteSerializer,
                          IngredientSerializer, RecipeReadSerializer,
                          RecipeWriteSerializer, ShoppingCartSerializer,
                          SubscribeSerializer, SubscribeUserSerializer,
                          TagSerializer,)


class CustomUserViewSet(djoser_views.UserViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=(IsAuthenticated,))
    def add_delete_subscribe(self, request, id):
        """Добавление/удаление подписки."""

        user = request.user
        author = get_object_or_404(User, id=id)

        if request.method == 'POST':
            serializer = SubscribeSerializer(author,
                                             data=request.data,
                                             context={"request": request})
            serializer.is_valid(raise_exception=True)
            Subscribe.objects.create(user=user, author=author)
            serializer.save()
            return Response({'detail': 'Подписка успешно создана.'},
                            status=status.HTTP_201_CREATED,)

        if request.method == 'DELETE':
            subscription = get_object_or_404(Subscribe,
                                             user=user,
                                             author=author)
            subscription.delete()
            return Response({'detail': 'Подписка успешно удалена.'},
                            status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'],
            permission_classes=(IsAuthenticated,))
    def subscriptions(self, request):
        """Отображает все подписки пользователя."""

        user = request.user
        queryset = User.objects.filter(subscribing__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = SubscribeUserSerializer(pages, many=True,
                                             context={'request': request})
        return self.get_paginated_response(serializer.data)


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет рецепта."""

    queryset = Recipe.objects.all()
    pagination_class = LimitPageNumberPagination
    permission_classes = (IsAuthenticatedOrReadOnly,)
    filterset_class = RecipeFilter
    filterset_fields = ('tags',)
    filter_backends = (DjangoFilterBackend,)

    def get_serializer_class(self):
        """Выбор сериализатора."""
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    @action(detail=True, methods=['post'],)
    def add_to_favorite(self, request, id):
        """Добавление рецепта в избранное."""

        serializer = FavoriteSerializer(
            data={'author': request.user.id,
                  'recipe': id, },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Рецепт добавлен в избранное.'},
                        status=status.HTTP_201_CREATED,)

    @action(detail=True, methods=['delete'],)
    def delete_from_favorite(self, request, id):
        """Удаление рецепта из избранных."""

        serializer = FavoriteSerializer(
            data={'author': request.user.id,
                  'recipe': id, },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        recipe = get_object_or_404(Recipe, id=id)
        favorites = recipe.favorites.filter(author=request.user)
        favorites.delete()
        return Response({'detail': 'Рецепт удален из избранного.'},
                        status=status.HTTP_204_NO_CONTENT,)

    @action(detail=True, methods=['post'],)
    def add_to_shopping_cart(self, request, id):
        """Добавление рецепта в список покупок."""

        serializer = ShoppingCartSerializer(
            data={'author': request.user.id,
                  'recipe': id, },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Рецепт добавлен в список покупок.'},
                        status=status.HTTP_201_CREATED,)

    @action(detail=True, methods=['delete'],)
    def delete_from_shopping_cart(self, request, id):
        """Удаление рецепта из списка покупок."""

        serializer = ShoppingCartSerializer(
            data={'author': request.user.id,
                  'recipe': id, },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        recipe = get_object_or_404(Recipe, id=id)
        shopping_cart = recipe.shopping_cart.filter(author=request.user)
        shopping_cart.delete()
        return Response({'detail': 'Рецепт удален из списка покупок.'},
                        status=status.HTTP_204_NO_CONTENT,)

    @action(detail=False, methods=['get'],)
    def download_shopping_cart(self, request):
        """"Скачать список покупок."""

        user = request.user
        if not user.shopping_cart.exists():
            return Response({'detail': 'Корзина пуста.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ingredients = RecipeIngredient.objects.filter(
            recipe__shopping_cart__author=request.user).values(
                'ingredient__name', 'ingredient__measurement_unit'
            ).annotate(amount=Sum('amount'))
        today = datetime.today()
        shopping_list = (f'Список покупок для: {user.get_full_name()}\n\n'
                         f'Дата: {today:%Y-%m-%d}\n\n')
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


class TagViewSet(viewsets.ModelViewSet):
    """Вьюсет Тегов."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (IsAdminOrReadOnly,)


class IngredientViewSet(viewsets.ModelViewSet):
    """Вьюсет Ингредиентов."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
