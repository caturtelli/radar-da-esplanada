"""Sincroniza popstate do contêiner Community Cloud com a aplicação embutida.

Sem navegação própria, dados externos, polling ou alteração de permissões.
O roteamento continua sendo o do Streamlit. A ponte só despacha seu evento
nativo quando o contêiner de mesma origem muda a URL pelo histórico.
"""
import streamlit.components.v1 as components

BRIDGE = r'''<script>
(() => {
  const app = window.parent;
  const host = app.parent;
  if (host === app) return;
  try {
    if (host.location.origin !== app.location.origin) return;
    const key = '__radarSameOriginHistoryBridge';
    const previous = host[key];
    if (previous) previous.dispose();
    let timer;
    const restore = () => {
      // Let the Cloud container finish its own URL update before notifying Streamlit.
      clearTimeout(timer);
      timer = host.setTimeout(() => {
        try {
          const target = new URL(app.location.href);
          target.search = host.location.search;
          if (app.location.search !== target.search) {
            app.history.replaceState(app.history.state, '', target.href);
          }
          app.dispatchEvent(new app.PopStateEvent('popstate', {state: app.history.state}));
        } catch (_) {
          // A frame that was replaced cannot be used; the next mount installs a fresh bridge.
        }
      }, 0);
    };
    host.addEventListener('popstate', restore);
    host[key] = {
      dispose() {
        host.removeEventListener('popstate', restore);
        host.clearTimeout(timer);
      }
    };
  } catch (_) {
    // Standalone/cross-origin embedding keeps Streamlit's native behavior untouched.
  }
})();
</script>'''


def install_history_bridge():
    components.html(BRIDGE, height=0, scrolling=False, tab_index=-1)
