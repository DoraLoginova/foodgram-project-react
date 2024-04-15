from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import (
    SAFE_METHODS,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly
)
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from api.filters import IngredientFilter, RecipeFilter
from api.pagination import LimitPageNumberPagination
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    ShoppingCartSerializer,
    TagSerializer,
    FavoriteSerializer,
)
from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Tag,
)


User = get_user_model()


class IngredientViewSet(ReadOnlyModelViewSet):
    """Ингредиенты."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filterset_class = IngredientFilter
    filter_backends = (filters.SearchFilter,)
    search_fields = ('^name',)


class TagViewSet(ReadOnlyModelViewSet):
    """Тэги."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class RecipeViewSet(ModelViewSet):
    """Рецепты."""

    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly | IsAuthenticatedOrReadOnly,)
    pagination_class = LimitPageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    @action(
        detail=True,
        methods=['post'],
        permission_classes=(IsAuthenticated,),)
    def favorite(self, request, pk):
        serializer = FavoriteSerializer(
            data={
                'user': request.user.pk,
                'recipe': pk,
            },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Рецепт добавлен в избранное.'},
            status=status.HTTP_201_CREATED,)

    @favorite.mapping.delete
    def delete_from_favorite(self, request, pk):
        serializer = FavoriteSerializer(
            data={
                'user': request.user.pk,
                'recipe': pk,
            },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        recipe = get_object_or_404(Recipe, pk=pk)
        favorites = recipe.favorites.filter(user=request.user)
        favorites.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated],)
    def shopping_cart(self, request, pk):
        serializer = ShoppingCartSerializer(
            data={
                'user': request.user.pk,
                'recipe': pk,
            },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Рецепт добавлен в список покупок.'},
            status=status.HTTP_201_CREATED,)

    @shopping_cart.mapping.delete
    def delete_from_shopping_cart(self, request, pk):
        serializer = ShoppingCartSerializer(
            data={
                'author': request.user.pk,
                'recipe': pk,
            },
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        recipe = get_object_or_404(Recipe, pk=pk)
        shopping_cart = recipe.shopping_cart.filter(user=request.user)
        shopping_cart.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        """Скачивание списка покупок с ингредиентами."""
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
