from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.forms import ModelForm
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Order, OrderItem, CustomerProfile, StoreUser, StoreBanner, Cart


class StoreBannerForm(ModelForm):
    class Meta:
        model  = StoreBanner
        fields = ('title', 'subtitle', 'image', 'cta_text', 'order', 'is_active')
        labels = {
            'title':    'Titre',
            'subtitle': 'Sous-titre',
            'image':    'Image',
            'cta_text': 'Texte bouton',
            'order':    'Ordre d\'affichage',
            'is_active':'Active',
        }


def _site_ids(user):
    return user.managed_sites.values_list('pk', flat=True)


@login_required
def boutique_orders(request):
    if request.user.is_superadmin:
        qs = Order.objects.select_related('customer__store_user').prefetch_related('items__site')
    else:
        qs = (Order.objects
              .filter(items__site_id__in=_site_ids(request.user))
              .distinct()
              .select_related('customer__store_user')
              .prefetch_related('items__site'))

    status_filter = request.GET.get('status', '')
    search        = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if search:
        if search.isdigit() and len(search) == 10:
            qs = qs.filter(items__voucher_codes__contains=search).distinct()
        else:
            qs = qs.filter(
                Q(reference__icontains=search) |
                Q(customer__full_name__icontains=search) |
                Q(customer__phone__icontains=search) |
                Q(plopplop_transaction_id__icontains=search)
            )

    total_count   = qs.count()
    total_revenue = qs.aggregate(t=Sum('total_htg'))['t'] or 0

    paginator = Paginator(qs.order_by('-created_at'), 50)
    orders    = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'boutique/orders.html', {
        'orders':         orders,
        'status_filter':  status_filter,
        'search':         search,
        'status_choices': Order.STATUS_CHOICES,
        'total_count':    total_count,
        'total_revenue':  total_revenue,
        'page_title':     'Commandes',
    })


@login_required
def boutique_order_detail(request, order_ref):
    if request.user.is_superadmin:
        order = get_object_or_404(
            Order.objects.select_related('customer__store_user').prefetch_related('items__tier', 'items__site'),
            reference=order_ref,
        )
    else:
        order = get_object_or_404(
            Order.objects.filter(items__site_id__in=_site_ids(request.user))
                 .distinct()
                 .select_related('customer__store_user')
                 .prefetch_related('items__tier', 'items__site'),
            reference=order_ref,
        )

    return render(request, 'boutique/order_detail.html', {
        'order':      order,
        'page_title': f'Commande {order.reference}',
    })


@login_required
def boutique_customers(request):
    search = request.GET.get('q', '').strip()

    if request.user.is_superadmin:
        qs = CustomerProfile.objects.select_related('store_user', 'preferred_site')
    else:
        ids = _site_ids(request.user)
        qs = (CustomerProfile.objects
              .filter(Q(orders__items__site_id__in=ids) | Q(preferred_site_id__in=ids))
              .distinct()
              .select_related('store_user', 'preferred_site'))

    if search:
        qs = qs.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))

    paginator  = Paginator(qs.order_by('-created_at'), 50)
    customers  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'boutique/customers.html', {
        'customers':  customers,
        'search':     search,
        'page_title': 'Profils clients',
    })


@login_required
def boutique_store_users(request):
    search = request.GET.get('q', '').strip()

    if request.user.is_superadmin:
        qs = StoreUser.objects.prefetch_related('profiles')
    else:
        ids = _site_ids(request.user)
        qs = (StoreUser.objects
              .filter(profiles__orders__items__site_id__in=ids)
              .distinct()
              .prefetch_related('profiles'))

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    paginator = Paginator(qs.order_by('-created_at'), 50)
    users     = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'boutique/store_users.html', {
        'users':      users,
        'search':     search,
        'page_title': 'Utilisateurs store',
    })


def _superadmin_required(request):
    if not request.user.is_superadmin:
        messages.error(request, "Accès réservé au super-admin.")
        return redirect('boutique:orders')
    return None


@login_required
def boutique_banners(request):
    guard = _superadmin_required(request)
    if guard:
        return guard
    banners = StoreBanner.objects.all().order_by('order')
    return render(request, 'boutique/banners.html', {
        'banners':    banners,
        'page_title': 'Bannières',
    })


@login_required
def boutique_banner_create(request):
    guard = _superadmin_required(request)
    if guard:
        return guard
    form = StoreBannerForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Bannière créée.")
        return redirect('boutique:banners')
    return render(request, 'boutique/banner_form.html', {
        'form':       form,
        'page_title': 'Nouvelle bannière',
        'action':     'Créer',
    })


@login_required
def boutique_banner_edit(request, pk):
    guard = _superadmin_required(request)
    if guard:
        return guard
    banner = get_object_or_404(StoreBanner, pk=pk)
    form = StoreBannerForm(request.POST or None, request.FILES or None, instance=banner)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Bannière mise à jour.")
        return redirect('boutique:banners')
    return render(request, 'boutique/banner_form.html', {
        'form':       form,
        'banner':     banner,
        'page_title': f'Modifier — {banner.title}',
        'action':     'Enregistrer',
    })


@login_required
@require_POST
def boutique_banner_delete(request, pk):
    guard = _superadmin_required(request)
    if guard:
        return guard
    banner = get_object_or_404(StoreBanner, pk=pk)
    banner.delete()
    messages.success(request, "Bannière supprimée.")
    return redirect('boutique:banners')


@login_required
@require_POST
def boutique_banner_toggle(request, pk):
    guard = _superadmin_required(request)
    if guard:
        return guard
    banner = get_object_or_404(StoreBanner, pk=pk)
    banner.is_active = not banner.is_active
    banner.save(update_fields=['is_active'])
    return redirect('boutique:banners')


@login_required
def boutique_carts(request):
    if request.user.is_superadmin:
        qs = Cart.objects.select_related('store_user').prefetch_related('items__tier', 'items__site')
    else:
        ids = _site_ids(request.user)
        qs = (Cart.objects
              .filter(items__site_id__in=ids)
              .distinct()
              .select_related('store_user')
              .prefetch_related('items__tier', 'items__site'))

    paginator = Paginator(qs.order_by('-created_at'), 50)
    carts     = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'boutique/carts.html', {
        'carts':      carts,
        'page_title': 'Paniers actifs',
    })
