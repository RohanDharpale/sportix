(() => {
  const $ = (s, root=document) => root.querySelector(s);
  const $$ = (s, root=document) => [...root.querySelectorAll(s)];
  const money = n => '₹' + Number(n || 0).toLocaleString('en-IN');
  const CART_KEY = 'sportix-cart-v1';
  let productsCache = [];
  let toastTimer;
  const toast = message => {
    const el = $('[data-toast]');
    if (!el) return;
    el.textContent = message; el.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
  };
  const getCart = () => { try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); } catch { return []; } };
  const setCart = cart => { localStorage.setItem(CART_KEY, JSON.stringify(cart)); renderCart(); };
  const countCart = cart => cart.reduce((sum, item) => sum + item.quantity, 0);
  const cartTotal = cart => cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const productById = id => productsCache.find(p => p.id === Number(id));
  async function fetchProduct(id) {
    let p = productById(id);
    if (p) return p;
    const response = await fetch(`/api/products/${id}`);
    if (!response.ok) throw new Error('Product not found');
    p = await response.json(); productsCache.push(p); return p;
  }
  async function addToCart(id) {
    try {
      const product = await fetchProduct(id);
      if (product.stock < 1) return toast('Sorry, this item is out of stock.');
      const cart = getCart();
      const item = cart.find(x => x.id === product.id);
      if (item) {
        if (item.quantity >= Math.min(product.stock, 20)) return toast('Maximum available quantity reached.');
        item.quantity++;
      } else cart.push({id: product.id, quantity: 1, name: product.name, price: product.price, image: product.image, category: product.category, stock: product.stock});
      setCart(cart); toast(`${product.name} added to your cart.`);
    } catch { toast('Could not add this item. Please try again.'); }
  }
  function renderCart() {
    const cart = getCart();
    $$('[data-cart-count]').forEach(el => el.textContent = countCart(cart));
    const count = $('[data-drawer-count]'); if (count) count.textContent = `(${countCart(cart)})`;
    const total = $('[data-drawer-total]'); if (total) total.textContent = money(cartTotal(cart));
    const items = $('[data-drawer-items]');
    if (!items) return;
    if (!cart.length) {
      items.innerHTML = '<div class="drawer-empty"><span style="font-size:38px">＋</span><b>Your cart is taking a breather.</b><p>Find something that gets you moving.</p><a class="btn btn-primary" href="/shop" data-close-cart>Explore the collection ↗</a></div>';
      return;
    }
    items.innerHTML = cart.map(item => `<div class="drawer-item"><img src="${escapeHtml(item.image)}" alt=""><div><h3>${escapeHtml(item.name)}</h3><small>${escapeHtml(item.category || '')}</small><strong>${money(item.price)}</strong><div class="qty-controls"><button data-cart-dec="${item.id}" aria-label="Decrease quantity">−</button><span>${item.quantity}</span><button data-cart-inc="${item.id}" aria-label="Increase quantity">+</button></div></div><button class="remove-item" data-cart-remove="${item.id}" aria-label="Remove ${escapeHtml(item.name)}">×</button></div>`).join('');
  }
  function escapeHtml(str) { return String(str ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function openCart() {
    $('[data-cart-overlay]')?.classList.add('open');
    $('[data-cart-drawer]')?.classList.add('open');
    $('[data-cart-drawer]')?.setAttribute('aria-hidden','false');
    document.body.style.overflow = 'hidden';
  }
  function closeCart() {
    $('[data-cart-overlay]')?.classList.remove('open');
    $('[data-cart-drawer]')?.classList.remove('open');
    $('[data-cart-drawer]')?.setAttribute('aria-hidden','true');
    document.body.style.overflow = '';
  }
  document.addEventListener('click', async e => {
    const add = e.target.closest('[data-add-product]');
    if (add) { e.preventDefault(); await addToCart(add.dataset.addProduct); return; }
    if (e.target.closest('[data-open-cart]')) { openCart(); return; }
    if (e.target.closest('[data-close-cart]') || e.target.matches('[data-cart-overlay]')) { closeCart(); return; }
    const inc = e.target.closest('[data-cart-inc]');
    const dec = e.target.closest('[data-cart-dec]');
    const rem = e.target.closest('[data-cart-remove]');
    if (inc || dec || rem) {
      const id = Number((inc || dec || rem).dataset.cartInc || (inc || dec || rem).dataset.cartDec || (inc || dec || rem).dataset.cartRemove);
      let cart = getCart();
      if (rem) cart = cart.filter(i => i.id !== id);
      else {
        const item = cart.find(i => i.id === id);
        if (item && inc) item.quantity = Math.min(item.quantity + 1, Math.min(item.stock || 20, 20));
        if (item && dec) item.quantity--;
        cart = cart.filter(i => i.quantity > 0);
      }
      setCart(cart); return;
    }
    if (e.target.closest('[data-mobile-menu]')) { $('.main-nav')?.classList.toggle('open'); return; }
    if (e.target.closest('[data-back-top]')) { window.scrollTo({top:0,behavior:'smooth'}); }
  });
  $('[data-cart-overlay]')?.addEventListener('click', closeCart);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeCart(); closeCheckout(); } });

  // Catalog page: API-driven search, filters, sorting and rendering.
  const grid = $('[data-product-grid]');
  if (grid) {
    const search = $('[data-shop-search]');
    const categoryInputs = $$('[data-category-filter]');
    const minInput = $('[data-min-price]');
    const maxInput = $('[data-max-price]');
    const slider = $('[data-price-slider]');
    const brandSelect = $('[data-brand-filter]');
    const sortSelect = $('[data-sort]');
    const resultCount = $('[data-result-count]');
    const emptyState = $('[data-empty-state]');
    let searchDebounce;
    const params = new URLSearchParams(location.search);
    const initialCategory = params.get('category') || '';
    categoryInputs.forEach(input => { if (input.value === initialCategory) input.checked = true; });
    if (search && params.get('q')) search.value = params.get('q');
    const updatePrice = () => { if (Number(maxInput.value) > 10000) slider.value = 10000; else slider.value = Math.max(0, Number(maxInput.value)||0); };
    slider?.addEventListener('input', () => { maxInput.value = slider.value; loadProducts(); });
    maxInput?.addEventListener('input', () => { updatePrice(); loadProducts(); });
    minInput?.addEventListener('change', loadProducts);
    categoryInputs.forEach(input => input.addEventListener('change', loadProducts));
    brandSelect?.addEventListener('change', loadProducts);
    sortSelect?.addEventListener('change', loadProducts);
    search?.addEventListener('input', () => { clearTimeout(searchDebounce); searchDebounce = setTimeout(loadProducts, 220); });
    $$('[data-clear-filters]').forEach(button => button.addEventListener('click', () => {
      if(search) search.value = '';
      categoryInputs.forEach(i => i.checked = false);
      if(minInput) minInput.value = 0;
      if(maxInput) maxInput.value = 10000;
      if(slider) slider.value = 10000;
      if(brandSelect) brandSelect.value = '';
      if(sortSelect) sortSelect.value = 'featured';
      loadProducts();
    }));
    function productCard(p) {
      return `<article class="product-card"><div class="product-image"><img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.name)}" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=700&q=80'"><span class="product-badge">${p.stock > 0 ? 'READY TO PLAY' : 'SOLD OUT'}</span></div><div class="product-info"><div class="product-meta"><span>${escapeHtml(p.category)}</span><span class="rating">★ ${Number(p.rating).toFixed(1)} (${p.reviews})</span></div><h3>${escapeHtml(p.name)}</h3><div class="product-meta"><span>${escapeHtml(p.brand)}</span><span>${p.stock > 0 ? 'In stock' : 'Out of stock'}</span></div><div class="product-bottom"><strong>${money(p.price)}</strong><button class="add-button" data-add-product="${p.id}" ${p.stock < 1 ? 'disabled' : ''} aria-label="Add ${escapeHtml(p.name)} to cart">${p.stock > 0 ? '+' : '−'}</button></div></div></article>`;
    }
    function renderActiveFilters() {
      const holder = $('[data-active-filters]'); if (!holder) return;
      const active = [];
      if (search?.value.trim()) active.push(['Search: ' + search.value.trim(), () => {search.value=''; loadProducts();}]);
      const cat = categoryInputs.find(i => i.checked)?.value; if (cat) active.push([cat, () => {categoryInputs.forEach(i=>i.checked=false);loadProducts();}]);
      if (brandSelect?.value) active.push([brandSelect.value, () => {brandSelect.value='';loadProducts();}]);
      if (Number(minInput?.value)>0 || Number(maxInput?.value)<10000) active.push([`${money(minInput.value)}–${money(maxInput.value)}`, () => {minInput.value=0;maxInput.value=10000;slider.value=10000;loadProducts();}]);
      holder.innerHTML = active.map((a,i)=>`<button class="active-filter" data-active-filter="${i}">${escapeHtml(a[0])}<span>×</span></button>`).join('');
      $$('[data-active-filter]', holder).forEach((el,i)=>el.addEventListener('click',active[i][1]));
      const count = $('[data-filter-count]'); if(count) count.textContent = active.length ? `(${active.length})` : '';
    }
    async function loadProducts() {
      const q = new URLSearchParams();
      if (search?.value.trim()) q.set('q',search.value.trim());
      const cat = categoryInputs.find(i=>i.checked)?.value; if(cat) q.set('category',cat);
      if(brandSelect?.value) q.set('brand',brandSelect.value);
      if(Number(minInput?.value)>0) q.set('min_price',minInput.value);
      if(Number(maxInput?.value)<10000) q.set('max_price',maxInput.value);
      if(sortSelect?.value) q.set('sort',sortSelect.value);
      grid.innerHTML = '<div class="loading-state">Finding your gear…</div>';
      try {
        const res = await fetch('/api/products?' + q.toString());
        const data = await res.json();
        productsCache = data.products || [];
        grid.innerHTML = productsCache.map(productCard).join('');
        if (!productsCache.length) grid.innerHTML = '';
        if (resultCount) resultCount.textContent = `${data.count} product${data.count===1?'':'s'} to match your game`;
        if (emptyState) emptyState.hidden = productsCache.length > 0;
        if (brandSelect) {
          const previous = brandSelect.value;
          brandSelect.innerHTML = '<option value="">All brands</option>' + data.brands.map(b=>`<option value="${escapeHtml(b)}">${escapeHtml(b)}</option>`).join('');
          brandSelect.value = previous;
        }
        renderActiveFilters();
        const url = new URL(location.href);
        ['q','category','brand','min_price','max_price','sort'].forEach(k=>url.searchParams.delete(k));
        q.forEach((v,k)=>url.searchParams.set(k,v));
        history.replaceState({},'',url.pathname + (url.search ? url.search : '') + url.hash);
      } catch {
        grid.innerHTML = '<p class="form-error">Products could not load. Check your connection and refresh.</p>';
      }
    }
    // Build the brand options from the first API response; preserve filter selections on subsequent calls.
    fetch('/api/products').then(r=>r.json()).then(data=>{
      if(brandSelect) brandSelect.innerHTML = '<option value="">All brands</option>' + data.brands.map(b=>`<option value="${escapeHtml(b)}">${escapeHtml(b)}</option>`).join('');
      loadProducts();
    }).catch(loadProducts);
    $('[data-back-top]')?.addEventListener('click', () => window.scrollTo({top:0,behavior:'smooth'}));
  }

  // Checkout UI is injected once so the cart drawer stays lightweight.
  const checkoutMarkup = `<div class="checkout-modal" data-checkout-modal role="dialog" aria-modal="true" aria-labelledby="checkout-title"><div class="checkout-box"><button class="checkout-close" data-close-checkout aria-label="Close checkout">×</button><form class="checkout-form" data-checkout-form><span class="eyebrow">ALMOST THERE</span><h2 id="checkout-title">Checkout.</h2><div class="form-grid"><div class="form-field full"><label for="co-name">Full name *</label><input id="co-name" name="customer_name" autocomplete="name" required maxlength="100"></div><div class="form-field"><label for="co-email">Email *</label><input id="co-email" name="email" type="email" autocomplete="email" required></div><div class="form-field"><label for="co-phone">Mobile number *</label><input id="co-phone" name="phone" type="tel" autocomplete="tel" pattern="[0-9+ -]{10,15}" required></div><div class="form-field full"><label for="co-address">Delivery address *</label><textarea id="co-address" name="address" autocomplete="street-address" required maxlength="500"></textarea></div><div class="form-field"><label for="co-city">City *</label><input id="co-city" name="city" autocomplete="address-level2" required maxlength="80"></div><div class="form-field"><label for="co-pincode">PIN code *</label><input id="co-pincode" name="pincode" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="postal-code" required></div></div><div class="form-field"><label>Payment method</label><div class="payment-options"><label><input type="radio" name="payment_method" value="Cash on Delivery" checked> Cash on Delivery</label><label><input type="radio" name="payment_method" value="UPI (demo)"> UPI (demo — no payment taken)</label><label><input type="radio" name="payment_method" value="Card (demo)"> Card (demo — no payment taken)</label></div></div><p class="form-error" data-checkout-error hidden></p><button class="btn btn-primary btn-block" type="submit" data-place-order>Place order <span>↗</span></button><p style="font-size:9px;color:#788181;line-height:1.6">Demo checkout. UPI and card selections do not charge you.</p></form><aside class="checkout-summary"><span class="eyebrow">YOUR ORDER</span><h3>Order summary</h3><div class="summary-items" data-checkout-items></div><div class="summary-total"><span>Total</span><strong data-checkout-total>₹0</strong></div></aside></div></div>`;
  document.body.insertAdjacentHTML('beforeend', checkoutMarkup);
  const modal = $('[data-checkout-modal]');
  function closeCheckout() { modal?.classList.remove('open'); document.body.style.overflow=''; }
  function renderCheckoutSummary() {
    const cart = getCart();
    $('[data-checkout-items]').innerHTML = cart.map(i=>`<div class="summary-item"><img src="${escapeHtml(i.image)}" alt=""><div><strong>${escapeHtml(i.name)}</strong><span>Qty ${i.quantity} · ${money(i.price)}</span></div><strong>${money(i.price*i.quantity)}</strong></div>`).join('');
    $('[data-checkout-total]').textContent = money(cartTotal(cart));
  }
  async function startCheckout() {
    closeCart();
    if (!getCart().length) { toast('Your cart is empty — add something first.'); return; }
    renderCheckoutSummary(); modal.classList.add('open'); document.body.style.overflow='hidden';
  }
  document.addEventListener('click', e => {
    if (e.target.closest('[data-drawer-checkout]')) { e.preventDefault(); startCheckout(); }
    if (e.target.closest('[data-close-checkout]') || e.target === modal) closeCheckout();
  });
  const checkoutForm = $('[data-checkout-form]');
  checkoutForm.addEventListener('submit', async e => {
    e.preventDefault();
    const error = $('[data-checkout-error]'), submit = $('[data-place-order]');
    error.hidden = true;
    if (!getCart().length) { error.textContent='Your cart is empty.'; error.hidden=false; return; }
    const form = new FormData(checkoutForm);
    const payload = Object.fromEntries(form.entries());
    payload.items = getCart().map(i=>({id:i.id,quantity:i.quantity}));
    submit.disabled = true; submit.textContent = 'Placing your order…';
    try {
      const response = await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to place your order.');
      localStorage.setItem('sportix-last-order',JSON.stringify(data));
      localStorage.removeItem(CART_KEY);
      window.location.href='/order-success';
    } catch (err) {
      error.textContent = err.message || 'Something went wrong. Please try again.'; error.hidden=false;
    } finally { submit.disabled=false; submit.innerHTML='Place order <span>↗</span>'; }
  });
  const lastOrder = (()=>{try{return JSON.parse(localStorage.getItem('sportix-last-order')||'null')}catch{return null}})();
  if (lastOrder && $('[data-success-number]')) {
    $('[data-success-number]').textContent=lastOrder.order_number;
    $('[data-success-total]').textContent=money(lastOrder.total);
    $('[data-success-order]').textContent='Order placed successfully';
  }
  $('[data-newsletter]')?.addEventListener('submit', e => {
    e.preventDefault();
    $('[data-newsletter-message]').textContent='Thanks! Newsletter signup is a demo feature.';
    e.target.reset();
  });
  renderCart();
})();


// Subtle scroll reveals and sticky-header feedback.
(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const header = document.querySelector('.site-header');
  const onScroll = () => header?.classList.toggle('scrolled', window.scrollY > 12);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
  if (reduce || !('IntersectionObserver' in window)) return;
  document.body.classList.add('reveal-ready');
  const targets = document.querySelectorAll('.section-heading,.category-card,.product-card,.manifesto-copy,.benefit,.footer-main > div,.admin-card,.stat-card,.dashboard-card');
  targets.forEach((el, i) => {
    el.setAttribute('data-reveal', '');
    if (el.matches('.category-card,.product-card,.benefit')) el.setAttribute('data-reveal-delay', String((i % 3) + 1));
  });
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -35px 0px' });
  targets.forEach(el => observer.observe(el));
})();
