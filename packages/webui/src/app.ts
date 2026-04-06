import { AppController } from './app/app-controller.js';
import { AppView } from './app/app-view.js';

const app = new AppController();
(window as any)._app = app;

const appView = new AppView(app);
document.body.appendChild(appView.container);
