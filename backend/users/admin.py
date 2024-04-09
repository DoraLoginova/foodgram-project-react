from django.contrib import admin
from django.contrib.auth import admin as auth_admin

from .models import User, Subscribe


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    list_display = ('id', 'username', 'email',
                    'first_name', 'last_name',)
    search_fields = ('username', 'first_name', 'last_name',)
    list_filter = ('email', 'first_name',)
    empty_value_display = '-пусто-'


@admin.register(Subscribe)
class SubscribeAdmin(admin.ModelAdmin):
    list_display = ('user', 'author',)
