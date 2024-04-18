from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import (SAFE_METHODS, IsAuthenticated,)
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
    SubscribeSerializer,
    SubscribeUserSerializer,
    TagSerializer,
    FavoriteSerializer,
)
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


class UserViewSet(UserViewSet):
    pagination_class = LimitPageNumberPagination

    def get_permissions(self):
        if self.action == 'me':
            return (IsAuthenticated(), )
        return super().get_permissions()

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, **kwargs):
        author = get_object_or_404(User, id=self.kwargs.get('id'))
        data = {
            'user': request.user.id,
            'author': id
        }
        serializer = SubscribeSerializer(data=data,
                                         context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        serializer = SubscribeUserSerializer(request, author)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def delete_subscribe(self, request, **kwargs):
        author = get_object_or_404(User, id=self.kwargs.get('id'))
        obj = Subscribe.objects.filter(
            user=request.user, author=author
        ).delete()
        if not obj[0]:
            return Response(
                {'errors': 'Подписка уже удалена!'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {'detail': 'Вы успешно подписались!'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=False,
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(subscribing__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = SubscribeSerializer(pages,
                                         many=True,
                                         context={'request': request})
        return self.get_paginated_response(serializer.data)


class IngredientViewSet(ReadOnlyModelViewSet):
    """Ингредиенты."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filterset_class = IngredientFilter
    filter_backends = (DjangoFilterBackend,)
    search_fields = ('^name',)


class TagViewSet(ReadOnlyModelViewSet):
    """Тэги."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class RecipeViewSet(ModelViewSet):
    """Рецепты."""

    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly,)
    pagination_class = LimitPageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    @staticmethod
    def addition(request, pk, serializers):
        """Метод добавления."""
        data = {
            'user': request.user.pk,
            'recipe': pk
        }
        serializer = serializers(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def deletion(model, user, pk):
        """Метод удаления."""
        obj = model.objects.filter(user=user, recipe__id=pk).delete()
        if not obj[0]:
            return Response(
                {'errors': 'Рецепт уже удален!'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {'errors': 'Рецепт успешно удален!'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=True,
        methods=['post'],
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk):
        return self.addition(
            request, pk, FavoriteSerializer)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk):
        return self.deletion(
            FavoriteRecipe, request.user, pk)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk):
        return self.addition(
            request, pk, ShoppingCartSerializer
        )

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk):
        return self.deletion(
            ShoppingCart, request.user, pk)

    @action(
        detail=False,
        permission_classes=[IsAuthenticated]
    )
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
            f'- {ingredient["ingredient__name"]}'
            f'({ingredient["ingredient__measurement_unit"]})'
            f' - {ingredient["amount"]}'
            for ingredient in ingredients
        ])
        shopping_list += f'\n\nFoodgram ({today:%Y})'

        filename = f'{user.username}_shopping_list.txt'
        response = HttpResponse(shopping_list, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response
