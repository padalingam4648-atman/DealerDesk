import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import App from './App';

// Design tokens & stylesheets
import './styles/variables.css';
import './styles/global.css';
import './styles/components.css';
import './styles/layout.css';
import './styles/landing.css';
import './styles/portal.css';
import './styles/print.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>
);
