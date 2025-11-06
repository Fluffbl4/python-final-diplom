from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken, Address


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Панель управления пользователями
    """
    model = User

    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company', 'position')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'type', 'company')
    list_filter = ('type', 'is_staff', 'is_active', 'company')
    search_fields = ('email', 'first_name', 'last_name', 'company')


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'url', 'user', 'state')
    list_filter = ('state',)
    search_fields = ('name', 'user__email')
    list_select_related = ('user',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')
    list_select_related = ('category',)


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'shop', 'external_id', 'price', 'quantity', 'price_rrc')
    list_filter = ('shop',)
    search_fields = ('product__name', 'shop__name', 'external_id')
    list_select_related = ('product', 'shop')


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_info', 'parameter', 'value')
    list_filter = ('parameter',)
    search_fields = ('product_info__product__name', 'parameter__name', 'value')
    list_select_related = ('product_info', 'parameter')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'state', 'total_price', 'dt', 'address', 'contact')
    list_filter = ('state', 'dt')
    search_fields = ('user__email', 'id')
    readonly_fields = ('dt', 'total_price')
    list_select_related = ('user', 'address', 'contact')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product_info', 'quantity', 'item_price')
    list_filter = ('order__state',)
    search_fields = ('order__id', 'product_info__product__name')
    readonly_fields = ('item_price',)
    list_select_related = ('order', 'product_info')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'city', 'street', 'phone')
    list_filter = ('city',)
    search_fields = ('user__email', 'city', 'street', 'phone')
    list_select_related = ('user',)


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at',)
    search_fields = ('user__email', 'key')
    list_select_related = ('user',)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'city', 'street', 'house', 'apartment', 'is_primary', 'created_at')
    list_filter = ('city', 'is_primary', 'created_at')
    search_fields = ('user__email', 'city', 'street')
    readonly_fields = ('created_at',)
    list_select_related = ('user',)