import { AppView } from './app/app-view.js';

(() => {
    const appView = new AppView();
    const appRoot = document.getElementById('app-root');
    if (!appRoot) {
        throw new Error('App root element not found');
    }
    appRoot.appendChild(appView.container);
})();
