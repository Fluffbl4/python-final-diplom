from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from requests import get
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json
from yaml import load as load_yaml, Loader
from django.db import transaction

from .celery_tasks import async_partner_update

from .models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken, User
from .serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, ContactSerializer
from .signals import new_user_registered, new_order


def str_to_bool(value):
    """Convert string to boolean"""
    if isinstance(value, bool):
        return value
    if value.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif value.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise ValueError(f"Invalid boolean value: {value}")

class RegisterAccount(APIView):
    """
    Для регистрации покупателей
    """

    # Регистрация методом POST

    def post(self, request, *args, **kwargs):
        """
            Process a POST request and create a new user.

            Args:
                request (Request): The Django request object.

            Returns:
                JsonResponse: The response indicating the status of the operation and any errors.
            """
        # проверяем обязательные аргументы
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):

            # проверяем пароль на сложность
            sad = 'asd'
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                # проверяем данные для уникальности имени пользователя

                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        """
                Подтверждает почтовый адрес пользователя.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        # проверяем обязательные аргументы
        if {'email', 'token'}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class AccountDetails(APIView):
    """
    A class for managing user account details.

    Methods:
    - get: Retrieve the details of the authenticated user.
    - post: Update the account details of the authenticated user.

    Attributes:
    - None
    """

    # получить данные
    def get(self, request: Request, *args, **kwargs):
        """
               Retrieve the details of the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the details of the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Редактирование методом POST
    def post(self, request, *args, **kwargs):
        """
                Update the account details of the authenticated user.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        # проверяем обязательные аргументы

        if 'password' in request.data:
            errors = {}
            # проверяем пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                request.user.set_password(request.data['password'])

        # проверяем остальные данные
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """

    def post(self, request, *args, **kwargs):
        """
        Authenticate a user.

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if {'email', 'password'}.issubset(request.data):
            try:
                # Ищем пользователя по email
                user = User.objects.get(email=request.data['email'])
            except User.DoesNotExist:
                return JsonResponse({'Status': False, 'Errors': 'Пользователь не найден'})

            # Проверяем пароль
            if user.check_password(request.data['password']):
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return JsonResponse({'Status': True, 'Token': token.key})
                else:
                    return JsonResponse({'Status': False, 'Errors': 'Аккаунт не активирован'})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неверный пароль'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
        A class for searching products.

        Methods:
        - get: Retrieve the product information based on the specified filters.

        Attributes:
        - None
        """

    def get(self, request: Request, *args, **kwargs):
        """
               Retrieve the product information based on the specified filters.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the product information.
               """
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # фильтруем и отбрасываем дуликаты
        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data)


class BasketView(APIView):
    """
    A class for managing the user's shopping basket.

    Methods:
    - get: Retrieve the items in the user's basket.
    - post: Add an item to the user's basket.
    - put: Update the quantity of an item in the user's basket.
    - delete: Remove an item from the user's basket.

    Attributes:
    - None
    """

    # получить корзину
    def get(self, request, *args, **kwargs):
        """
        Retrieve the items in the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the items in the user's basket.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        try:
            basket = Order.objects.filter(
                user_id=request.user.id, state='basket').prefetch_related(
                'ordered_items__product_info__product__category',
                'ordered_items__product_info__product_parameters__parameter').annotate(
                total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

            # Если корзина не существует, создаем пустую
            if not basket.exists():
                empty_basket = {
                    'id': None,
                    'state': 'basket',
                    'ordered_items': [],
                    'total_sum': 0
                }
                return Response(empty_basket)

            serializer = OrderSerializer(basket, many=True)

            # Добавляем проверку доступности товаров
            basket_data = serializer.data[0] if serializer.data else {}
            if basket_data.get('ordered_items'):
                for item in basket_data['ordered_items']:
                    product_info = ProductInfo.objects.get(id=item['product_info'])
                    item['available_quantity'] = product_info.quantity
                    item['is_available'] = item['quantity'] <= product_info.quantity

            return Response(basket_data)

        except Exception as e:
            return JsonResponse({'Status': False, 'Error': str(e)}, status=400)

    # редактировать корзину
    def post(self, request, *args, **kwargs):
        """
        Add items to the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_data = request.data.get('items')
        if items_data:
            try:
                # Обрабатываем оба формата: строку JSON и готовый объект
                if isinstance(items_data, str):
                    # Если items - это строка, парсим её как JSON
                    items_dict = load_json(items_data)
                elif isinstance(items_data, (list, dict)):
                    # Если items - это уже список/словарь, используем как есть
                    items_dict = items_data
                else:
                    return JsonResponse({'Status': False, 'Errors': 'Неверный формат данных'})

            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                # Обеспечиваем что items_dict это список
                if isinstance(items_dict, dict):
                    items_dict = [items_dict]

                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_created = 0
                errors = []

                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)

                    if serializer.is_valid():
                        # Проверяем доступность товара
                        product_info_id = order_item.get('product_info')
                        quantity = order_item.get('quantity', 1)

                        try:
                            product_info = ProductInfo.objects.get(id=product_info_id)
                            if quantity > product_info.quantity:
                                errors.append(
                                    f'Недостаточно товара "{product_info.product.name}". Доступно: {product_info.quantity}')
                                continue

                            # Проверяем не добавлен ли уже товар в корзину
                            existing_item = OrderItem.objects.filter(
                                order=basket,
                                product_info=product_info
                            ).first()

                            if existing_item:
                                # Если товар уже есть, обновляем количество
                                new_quantity = existing_item.quantity + quantity
                                if new_quantity > product_info.quantity:
                                    errors.append(
                                        f'Недостаточно товара "{product_info.product.name}". Доступно: {product_info.quantity}, запрошено: {new_quantity}')
                                    continue
                                existing_item.quantity = new_quantity
                                existing_item.save()
                                objects_created += 1
                            else:
                                # Создаем новый элемент корзины
                                try:
                                    serializer.save()
                                    objects_created += 1
                                except IntegrityError as error:
                                    errors.append(str(error))

                        except ProductInfo.DoesNotExist:
                            errors.append(f'Товар с ID {product_info_id} не найден')

                    else:
                        errors.extend(serializer.errors)

                if errors:
                    return JsonResponse({'Status': False, 'Errors': errors}, status=400)

                # Пересчитываем общую стоимость корзины
                self._update_basket_total(basket.id)

                return JsonResponse({
                    'Status': True,
                    'Создано объектов': objects_created,
                    'Message': 'Товары добавлены в корзину'
                })

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить товары из корзины
    def delete(self, request, *args, **kwargs):
        """
        Remove items from the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            objects_deleted = False

            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]

                # Пересчитываем общую стоимость корзины
                self._update_basket_total(basket.id)

                return JsonResponse({
                    'Status': True,
                    'Удалено объектов': deleted_count,
                    'Message': 'Товары удалены из корзины'
                })

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # добавить позиции в корзину
    def put(self, request, *args, **kwargs):
        """
        Update the items in the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_data = request.data.get('items')
        if items_data:
            try:
                # Обрабатываем оба формата: строку JSON и готовый объект
                if isinstance(items_data, str):
                    # Если items - это строка, парсим её как JSON
                    items_dict = load_json(items_data)
                elif isinstance(items_data, (list, dict)):
                    # Если items - это уже список/словарь, используем как есть
                    items_dict = items_data
                else:
                    return JsonResponse({'Status': False, 'Errors': 'Неверный формат данных'})

            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                # Обеспечиваем что items_dict это список
                if isinstance(items_dict, dict):
                    items_dict = [items_dict]

                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0
                errors = []

                for order_item in items_dict:
                    if type(order_item['id']) == int and type(order_item['quantity']) == int:
                        item_id = order_item['id']
                        new_quantity = order_item['quantity']

                        try:
                            basket_item = OrderItem.objects.get(order_id=basket.id, id=item_id)
                            product_info = basket_item.product_info

                            # Проверяем доступность товара
                            if new_quantity > product_info.quantity:
                                errors.append(
                                    f'Недостаточно товара "{product_info.product.name}". Доступно: {product_info.quantity}')
                                continue

                            if new_quantity <= 0:
                                # Удаляем товар если количество 0 или меньше
                                basket_item.delete()
                            else:
                                basket_item.quantity = new_quantity
                                basket_item.save()
                                objects_updated += 1

                        except OrderItem.DoesNotExist:
                            errors.append(f'Товар с ID {item_id} не найден в корзине')

                if errors:
                    return JsonResponse({'Status': False, 'Errors': errors}, status=400)

                # Пересчитываем общую стоимость корзины
                self._update_basket_total(basket.id)

                return JsonResponse({
                    'Status': True,
                    'Обновлено объектов': objects_updated,
                    'Message': 'Корзина обновлена'
                })

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def _update_basket_total(self, basket_id):
        """
        Пересчет общей стоимости корзины
        """
        try:
            from django.db.models import Sum, F
            basket = Order.objects.get(id=basket_id)
            total_sum = OrderItem.objects.filter(
                order=basket
            ).aggregate(
                total=Sum(F('quantity') * F('product_info__price'))
            )['total'] or 0

            # Сохраняем общую стоимость (если в модели есть такое поле)
            if hasattr(basket, 'total_price'):
                basket.total_price = total_sum
                basket.save()

        except Exception as e:
            print(f"Error updating basket total: {e}")

class PartnerUpdate(APIView):
    """
    A class for updating partner information.

    Methods:
    - post: Update the partner information.

    Attributes:
    - None
    """

    def post(self, request, *args, **kwargs):
        """
        Update the partner price list information.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        # Проверяем наличие файла или URL
        file = request.FILES.get('file')
        url = request.data.get('url')

        # Если нет ни файла ни URL - возвращаем ошибку
        if not file and not url:
            return JsonResponse({'Status': False, 'Error': 'Не указаны файл или URL'}, status=400)

        # Проверяем параметр async для асинхронной обработки
        async_mode = request.data.get('async', 'false').lower() in ('true', '1', 'yes')

        try:
            if file:
                # Обработка загруженного файла
                if not file.name.endswith(('.yaml', '.yml')):
                    return JsonResponse({'Status': False, 'Error': 'Wrong file format. Only YAML files are supported'},
                                        status=400)

                yaml_data = file.read().decode('utf-8')

                if async_mode:
                    # Асинхронная обработка файла
                    from .celery_tasks import async_partner_update
                    task = async_partner_update.delay(request.user.id, yaml_data, None)
                    return JsonResponse({
                        'Status': True,
                        'Message': 'Import started in background',
                        'task_id': task.id
                    }, status=202)
                else:
                    # Синхронная обработка файла
                    return self.sync_import_from_data(request.user, yaml_data)

            elif url:
                # Обработка URL
                validate_url = URLValidator()
                try:
                    validate_url(url)
                except ValidationError as e:
                    return JsonResponse({'Status': False, 'Error': str(e)}, status=400)

                if async_mode:
                    # Асинхронная обработка URL
                    from .celery_tasks import async_partner_update
                    task = async_partner_update.delay(request.user.id, None, url)
                    return JsonResponse({
                        'Status': True,
                        'Message': 'Import started in background',
                        'task_id': task.id
                    }, status=202)
                else:
                    # Синхронная обработка URL (существующая логика)
                    return self.sync_import_from_url(request.user, url)

        except Exception as e:
            return JsonResponse({'Status': False, 'Error': str(e)}, status=400)

    def sync_import_from_url(self, user, url):
        """
        Синхронный импорт из URL (сохраняем существующую логику)
        """
        stream = get(url).content
        data = load_yaml(stream, Loader=Loader)

        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user.id)

        # Импорт категорий
        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
            category_object.shops.add(shop.id)
            category_object.save()

        # Удаляем старые товары и импортируем новые
        ProductInfo.objects.filter(shop_id=shop.id).delete()

        for item in data['goods']:
            product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

            product_info = ProductInfo.objects.create(product_id=product.id,
                                                      external_id=item['id'],
                                                      model=item['model'],
                                                      price=item['price'],
                                                      price_rrc=item['price_rrc'],
                                                      quantity=item['quantity'],
                                                      shop_id=shop.id)

            # Импорт параметров
            for name, value in item['parameters'].items():
                parameter_object, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(product_info_id=product_info.id,
                                                parameter_id=parameter_object.id,
                                                value=value)

        return JsonResponse({'Status': True, 'Message': 'Import from URL completed successfully'})

    def sync_import_from_data(self, user, yaml_data):
        """
        Синхронный импорт из YAML данных
        """
        data = load_yaml(yaml_data, Loader=Loader)

        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user.id)

        # Импорт категорий
        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
            category_object.shops.add(shop.id)
            category_object.save()

        # Удаляем старые товары и импортируем новые
        ProductInfo.objects.filter(shop_id=shop.id).delete()

        imported_count = 0
        for item in data['goods']:
            product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

            product_info = ProductInfo.objects.create(product_id=product.id,
                                                      external_id=item['id'],
                                                      model=item['model'],
                                                      price=item['price'],
                                                      price_rrc=item['price_rrc'],
                                                      quantity=item['quantity'],
                                                      shop_id=shop.id)
            imported_count += 1

            # Импорт параметров
            for name, value in item['parameters'].items():
                parameter_object, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(product_info_id=product_info.id,
                                                parameter_id=parameter_object.id,
                                                value=value)

        return JsonResponse({
            'Status': True,
            'Message': 'Import from file completed successfully',
            'Details': {
                'products_imported': imported_count,
                'categories_processed': len(data['categories'])
            }
        })


class PartnerState(APIView):
    """
       A class for managing partner state.

       Methods:
       - get: Retrieve the state of the partner.

       Attributes:
       - None
       """
    # получить текущий статус
    def get(self, request, *args, **kwargs):
        """
               Retrieve the state of the partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the state of the partner.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # изменить текущий статус
    def post(self, request, *args, **kwargs):
        """
               Update the state of a partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)
        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=str_to_bool(state))
                return JsonResponse({'Status': True})
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerOrders(APIView):
    """
    Класс для получения заказов поставщиками
     Methods:
    - get: Retrieve the orders associated with the authenticated partner.

    Attributes:
    - None
    """

    def get(self, request, *args, **kwargs):
        """
               Retrieve the orders associated with the authenticated partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the orders associated with the partner.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """
    A class for managing contact information.
    """

    def get(self, request, *args, **kwargs):
        """
        Retrieve the contact information of the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Create a new contact for the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'city', 'street', 'phone'}.issubset(request.data):
            # Создаем копию данных и добавляем user_id
            data = request.data.copy()
            data['user'] = request.user.id

            serializer = ContactSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def delete(self, request, *args, **kwargs):
        """
        Delete the contact of the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def put(self, request, *args, **kwargs):
        """
        Update the contact information of the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                print(contact)
                if contact:
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True})
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class OrderView(APIView):
    """
    Класс для получения и размещения заказов пользователями
    Methods:
    - get: Retrieve the details of a specific order.
    - post: Create a new order.
    - put: Update the details of a specific order.
    - delete: Delete a specific order.

    Attributes:
    - None
    """

    # получить мои заказы
    def get(self, request, *args, **kwargs):
        """
        Retrieve the details of user orders.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the details of the order.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        try:
            orders = Order.objects.filter(
                user_id=request.user.id).exclude(state='basket').prefetch_related(
                'ordered_items__product_info__product__category',
                'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
                total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

            # Если заказов нет, возвращаем пустой список
            if not orders.exists():
                return JsonResponse({'Status': True, 'Orders': []})

            serializer = OrderSerializer(orders, many=True)

            # Добавляем дополнительную информацию о заказах
            orders_data = []
            for order_data in serializer.data:
                # Добавляем информацию о контакте
                if order_data.get('contact'):
                    try:
                        contact = Contact.objects.get(id=order_data['contact'])
                        order_data['contact_details'] = {
                            'id': contact.id,
                            'phone': contact.phone,
                            'city': contact.city,
                            'street': contact.street,
                            'house': contact.house,
                            'apartment': contact.apartment
                        }
                    except Contact.DoesNotExist:
                        order_data['contact_details'] = None

                # Добавляем детальную информацию о товарах
                if order_data.get('ordered_items'):
                    for item in order_data['ordered_items']:
                        try:
                            product_info = ProductInfo.objects.get(id=item['product_info'])
                            item['product_name'] = product_info.product.name
                            item['shop_name'] = product_info.shop.name
                            item['price'] = product_info.price
                            item['total_price'] = item['quantity'] * product_info.price
                        except ProductInfo.DoesNotExist:
                            item['product_name'] = 'Товар не найден'
                            item['shop_name'] = 'Магазин не найден'

                orders_data.append(order_data)

            return JsonResponse({'Status': True, 'Orders': orders_data})

        except Exception as e:
            return JsonResponse({'Status': False, 'Error': str(e)}, status=400)

    # разместить заказ из корзины
    def post(self, request, *args, **kwargs):
        """
        Put an order and send a notification.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        # Вариант 1: подтверждение заказа с указанием ID корзины и контакта
        if {'id', 'contact'}.issubset(request.data):
            if str(request.data['id']).isdigit():
                try:
                    with transaction.atomic():
                        # Находим корзину пользователя
                        basket = Order.objects.get(
                            user_id=request.user.id,
                            id=request.data['id'],
                            state='basket'
                        )

                        # Проверяем что корзина не пуста
                        if not basket.ordered_items.exists():
                            return JsonResponse({'Status': False, 'Error': 'Корзина пуста'}, status=400)

                        # Проверяем существование контакта
                        try:
                            contact = Contact.objects.get(
                                id=request.data['contact'],
                                user_id=request.user.id
                            )
                        except Contact.DoesNotExist:
                            return JsonResponse({'Status': False, 'Error': 'Контакт не найден'}, status=400)

                        # Проверяем доступность всех товаров в корзине
                        unavailable_items = []
                        for item in basket.ordered_items.all():
                            if item.quantity > item.product_info.quantity:
                                unavailable_items.append({
                                    'product': item.product_info.product.name,
                                    'requested': item.quantity,
                                    'available': item.product_info.quantity
                                })

                        if unavailable_items:
                            return JsonResponse({
                                'Status': False,
                                'Error': 'Недостаточно товаров на складе',
                                'UnavailableItems': unavailable_items
                            }, status=400)

                        # Обновляем количество товаров на складе
                        for item in basket.ordered_items.all():
                            item.product_info.quantity -= item.quantity
                            item.product_info.save()

                        # Подтверждаем заказ
                        basket.contact = contact
                        basket.state = 'new'
                        basket.save()

                        # ДОБАВЛЕНО: Импорт внутри блока try для избежания ошибок импорта
                        try:
                            from backend.celery_tasks import send_order_confirmation_email
                            send_order_confirmation_email.delay(basket.id)
                        except ImportError as e:
                            print(f"Celery task import error: {e}")
                            # Продолжаем выполнение даже если celery недоступен

                        # Отправляем сигнал (если нужно)
                        try:
                            from django.db.models.signals import post_save
                            from django.dispatch import receiver
                            new_order.send(sender=self.__class__, user_id=request.user.id)
                        except Exception as e:
                            print(f"Signal error: {e}")

                        return JsonResponse({
                            'Status': True,
                            'Message': 'Заказ успешно оформлен',
                            'OrderID': basket.id,
                            'TotalPrice': basket.ordered_items.aggregate(
                                total=Sum(F('quantity') * F('product_info__price'))
                            )['total'] or 0
                        })

                except Order.DoesNotExist:
                    return JsonResponse({'Status': False, 'Error': 'Корзина не найдена'}, status=404)
                except IntegrityError as error:
                    return JsonResponse({'Status': False, 'Error': f'Ошибка базы данных: {str(error)}'}, status=400)
                except Exception as error:
                    return JsonResponse({'Status': False, 'Error': str(error)}, status=400)

        # Вариант 2: подтверждение текущей корзины пользователя
        elif 'contact' in request.data:
            try:
                with transaction.atomic():
                    # Находим активную корзину пользователя
                    basket = Order.objects.filter(
                        user_id=request.user.id,
                        state='basket'
                    ).prefetch_related('ordered_items').first()

                    if not basket or not basket.ordered_items.exists():
                        return JsonResponse({'Status': False, 'Error': 'Корзина пуста'}, status=400)

                    # Проверяем существование контакта
                    try:
                        contact = Contact.objects.get(
                            id=request.data['contact'],
                            user_id=request.user.id
                        )
                    except Contact.DoesNotExist:
                        return JsonResponse({'Status': False, 'Error': 'Контакт не найден'}, status=400)

                    # Проверяем доступность товаров
                    unavailable_items = []
                    for item in basket.ordered_items.all():
                        if item.quantity > item.product_info.quantity:
                            unavailable_items.append({
                                'product': item.product_info.product.name,
                                'requested': item.quantity,
                                'available': item.product_info.quantity
                            })

                    if unavailable_items:
                        return JsonResponse({
                            'Status': False,
                            'Error': 'Недостаточно товаров на складе',
                            'UnavailableItems': unavailable_items
                        }, status=400)

                    # Обновляем количество товаров
                    for item in basket.ordered_items.all():
                        item.product_info.quantity -= item.quantity
                        item.product_info.save()

                    # Подтверждаем заказ
                    basket.contact = contact
                    basket.state = 'new'
                    basket.save()

                    # ДОБАВЛЕНО: Импорт внутри блока try для избежания ошибок импорта
                    try:
                        from backend.celery_tasks import send_order_confirmation_email
                        send_order_confirmation_email.delay(basket.id)
                    except ImportError as e:
                        print(f"Celery task import error: {e}")
                        # Продолжаем выполнение даже если celery недоступен

                    try:
                        new_order.send(sender=self.__class__, user_id=request.user.id)
                    except Exception as e:
                        print(f"Signal error: {e}")

                    return JsonResponse({
                        'Status': True,
                        'Message': 'Заказ успешно оформлен',
                        'OrderID': basket.id,
                        'TotalPrice': basket.ordered_items.aggregate(
                            total=Sum(F('quantity') * F('product_info__price'))
                        )['total'] or 0
                    })

            except Exception as error:
                return JsonResponse({'Status': False, 'Error': str(error)}, status=400)

        return JsonResponse({'Status': False, 'Error': 'Не указаны все необходимые аргументы'})

    # добавить методы put и delete для полноты API
    def put(self, request, *args, **kwargs):
        """
        Update order details (например, изменение контакта доставки)

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        order_id = request.data.get('id')
        contact_id = request.data.get('contact')

        if not order_id or not contact_id:
            return JsonResponse({'Status': False, 'Error': 'Не указаны ID заказа или контакта'}, status=400)

        try:
            # Находим заказ пользователя (только заказы в статусе 'new')
            order = Order.objects.get(
                user_id=request.user.id,
                id=order_id,
                state='new'  # Можно изменять только новые заказы
            )

            # Проверяем существование контакта
            contact = Contact.objects.get(id=contact_id, user_id=request.user.id)

            # Обновляем контакт
            order.contact = contact
            order.save()

            return JsonResponse({
                'Status': True,
                'Message': 'Контакт доставки обновлен'
            })

        except Order.DoesNotExist:
            return JsonResponse({'Status': False, 'Error': 'Заказ не найден или нельзя изменить'}, status=404)
        except Contact.DoesNotExist:
            return JsonResponse({'Status': False, 'Error': 'Контакт не найден'}, status=404)
        except Exception as e:
            return JsonResponse({'Status': False, 'Error': str(e)}, status=400)

    def delete(self, request, *args, **kwargs):
        """
        Cancel an order (только заказы в статусе 'new')

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        order_id = request.data.get('id')
        if not order_id:
            return JsonResponse({'Status': False, 'Error': 'Не указан ID заказа'}, status=400)

        try:
            with transaction.atomic():
                # Находим заказ пользователя (только новые заказы можно отменять)
                order = Order.objects.get(
                    user_id=request.user.id,
                    id=order_id,
                    state='new'
                )

                # Возвращаем товары на склад
                for item in order.ordered_items.all():
                    item.product_info.quantity += item.quantity
                    item.product_info.save()

                # Отменяем заказ
                order.state = 'canceled'
                order.save()

                # ДОБАВЛЕНО: Импорт внутри блока try для избежания ошибок импорта
                try:
                    from backend.celery_tasks import send_order_status_update_email
                    send_order_status_update_email.delay(order.id, 'new', 'canceled')
                except ImportError as e:
                    print(f"Celery task import error: {e}")
                    # Продолжаем выполнение даже если celery недоступен

                return JsonResponse({
                    'Status': True,
                    'Message': 'Заказ отменен'
                })

        except Order.DoesNotExist:
            return JsonResponse({'Status': False, 'Error': 'Заказ не найден или нельзя отменить'}, status=404)
        except Exception as e:
            return JsonResponse({'Status': False, 'Error': str(e)}, status=400)