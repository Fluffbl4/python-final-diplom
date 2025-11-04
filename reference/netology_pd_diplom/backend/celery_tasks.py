from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from yaml import load as load_yaml, Loader
from requests import get
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from .models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, Contact, \
    ConfirmEmailToken


@shared_task
def async_partner_update(user_id, yaml_data, url):
    """
    Асинхронная задача для импорта товаров
    """
    try:
        from .models import User

        user = User.objects.get(id=user_id)

        if user.type != 'shop':
            return {'Status': False, 'Error': 'User is not a shop'}

        if yaml_data:
            # Импорт из YAML данных
            data = load_yaml(yaml_data, Loader=Loader)
            result = import_data(user, data)
        elif url:
            # Импорт из URL
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return {'Status': False, 'Error': str(e)}

            stream = get(url).content
            data = load_yaml(stream, Loader=Loader)
            result = import_data(user, data)
        else:
            return {'Status': False, 'Error': 'No data provided'}

        # Отправка email отчета
        send_import_report.delay(
            user.email,
            result['categories_processed'],
            result['products_imported']
        )

        return {
            'Status': True,
            'Message': 'Import completed successfully',
            'Details': result
        }

    except Exception as e:
        # Отправка email об ошибке
        if 'user' in locals():
            send_import_error.delay(user.email, str(e))
        return {'Status': False, 'Error': str(e)}


def import_data(user, data):
    """
    Общая функция импорта данных
    """
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

    return {
        'categories_processed': len(data['categories']),
        'products_imported': imported_count
    }


@shared_task
def send_import_report(email, categories_count, products_count):
    """Отправка отчета об импорте"""
    subject = 'Отчет об импорте товаров'
    message = f"""
    Импорт товаров завершен успешно!

    Статистика:
    - Обработано категорий: {categories_count}
    - Импортировано товаров: {products_count}

    Спасибо за использование нашей системы!
    """

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


@shared_task
def send_import_error(email, error_message):
    """Отправка уведомления об ошибке импорта"""
    subject = 'Ошибка при импорте товаров'
    message = f"""
    При импорте товаров произошла ошибка:

    {error_message}

    Пожалуйста, проверьте формат файла и попробуйте снова.
    """

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


@shared_task
def send_order_confirmation_email(order_id):
    """
    Отправка подтверждения заказа клиенту
    """
    try:
        from .models import Order, OrderItem

        # Получаем заказ с связанными данными
        order = Order.objects.select_related('user', 'contact').get(id=order_id)
        user = order.user

        # Получаем товары заказа
        order_items = OrderItem.objects.filter(order=order).select_related(
            'product_info', 'product_info__product', 'product_info__shop'
        )

        # Формируем детали заказа
        items_details = []
        total_price = 0

        for item in order_items:
            item_total = item.quantity * item.product_info.price
            total_price += item_total
            items_details.append(
                f"- {item.product_info.product.name} "
                f"({item.product_info.shop.name}): "
                f"{item.quantity} шт. × {item.product_info.price} руб. = {item_total} руб."
            )

        items_text = "\n".join(items_details)

        # Формируем информацию о доставке
        delivery_info = ""
        if order.contact:
            contact = order.contact
            delivery_info = f"""
Адрес доставки:
Город: {contact.city}
Улица: {contact.street}
Дом: {contact.house}
{f'Квартира: {contact.apartment}' if contact.apartment else ''}
Телефон: {contact.phone}
"""

        subject = f'Подтверждение заказа #{order_id}'
        message = f"""
Уважаемый(ая) {user.first_name or user.email}!

Ваш заказ #{order_id} успешно оформлен.

Детали заказа:
{items_text}

Общая стоимость: {total_price} руб.
Статус: Новый
Дата оформления: {order.dt.strftime('%d.%m.%Y %H:%M')}
{delivery_info}
Вы можете отслеживать статус вашего заказа в личном кабинете.

Спасибо за покупку!

С уважением,
Команда магазина
"""

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        # Также отправляем уведомление администратору
        send_new_order_notification.delay(order_id)

        return f"Confirmation email sent for order {order_id}"

    except Order.DoesNotExist:
        return f"Order {order_id} not found"
    except Exception as e:
        return f"Error sending confirmation email: {str(e)}"


@shared_task
def send_new_order_notification(order_id):
    """
    Уведомление администратора о новом заказе
    """
    try:
        from .models import Order, OrderItem

        order = Order.objects.select_related('user', 'contact').get(id=order_id)
        user = order.user
        order_items = OrderItem.objects.filter(order=order).select_related(
            'product_info', 'product_info__product', 'product_info__shop'
        )

        # Формируем детали заказа для администратора
        items_details = []
        total_price = 0

        for item in order_items:
            item_total = item.quantity * item.product_info.price
            total_price += item_total
            items_details.append(
                f"- {item.product_info.product.name} "
                f"(Магазин: {item.product_info.shop.name}): "
                f"{item.quantity} шт. × {item.product_info.price} руб. = {item_total} руб."
            )

        items_text = "\n".join(items_details)

        delivery_info = ""
        if order.contact:
            contact = order.contact
            delivery_info = f"""
Контактная информация:
Город: {contact.city}
Улица: {contact.street}
Дом: {contact.house}
{f'Квартира: {contact.apartment}' if contact.apartment else ''}
Телефон: {contact.phone}
"""

        user_info = f"Пользователь: {user.email}"
        if user.first_name and user.last_name:
            user_info += f"\nИмя: {user.first_name} {user.last_name}"

        subject = f'Новый заказ #{order_id}'
        message = f"""
Поступил новый заказ!

Детали заказа #{order_id}:
{user_info}
Дата: {order.dt.strftime('%d.%m.%Y %H:%M')}
{delivery_info}
Товары:
{items_text}

Общая стоимость: {total_price} руб.

Требуется обработка заказа.
"""

        # Отправляем администратору (можно указать несколько email)
        admin_emails = getattr(settings, 'ADMIN_EMAILS', [settings.DEFAULT_FROM_EMAIL])

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=False,
        )

        return f"Admin notification sent for order {order_id}"

    except Exception as e:
        return f"Error sending admin notification: {str(e)}"


@shared_task
def send_order_status_update_email(order_id, old_status, new_status):
    """
    Уведомление об изменении статуса заказа
    """
    try:
        from .models import Order

        order = Order.objects.select_related('user').get(id=order_id)
        user = order.user

        # Словарь для отображения статусов
        status_display = {
            'basket': 'В корзине',
            'new': 'Новый',
            'confirmed': 'Подтвержден',
            'assembled': 'Собран',
            'sent': 'Отправлен',
            'delivered': 'Доставлен',
            'canceled': 'Отменен'
        }

        old_status_display = status_display.get(old_status, old_status)
        new_status_display = status_display.get(new_status, new_status)

        subject = f'Статус вашего заказа #{order_id} изменен'
        message = f"""
Уважаемый(ая) {user.first_name or user.email}!

Статус вашего заказа #{order_id} изменен:
Было: {old_status_display}
Стало: {new_status_display}

Дата изменения: {order.dt.strftime('%d.%m.%Y %H:%M')}

Вы можете отслеживать статус вашего заказа в личном кабинете.

С уважением,
Команда магазина
"""

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return f"Status update email sent for order {order_id}"

    except Order.DoesNotExist:
        return f"Order {order_id} not found"
    except Exception as e:
        return f"Error sending status update: {str(e)}"


@shared_task
def send_user_registration_email(user_id):
    """
    Отправка email подтверждения регистрации
    """
    try:
        from .models import User, ConfirmEmailToken

        user = User.objects.get(id=user_id)

        # Создаем токен подтверждения
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=user.id)

        subject = 'Подтверждение регистрации'
        message = f"""
Уважаемый(ая) {user.first_name or user.email}!

Благодарим вас за регистрацию в нашем магазине!

Для завершения регистрации пожалуйста подтвердите ваш email, перейдя по ссылке:
{getattr(settings, 'BASE_URL', 'http://localhost:8000')}/user/register/confirm?token={token.key}

Или используйте токен подтверждения: {token.key}

С уважением,
Команда магазина
"""

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return f"Registration email sent for user {user.email}"

    except Exception as e:
        return f"Error sending registration email: {str(e)}"