from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from yaml import load as load_yaml, Loader
from requests import get
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from .models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter


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