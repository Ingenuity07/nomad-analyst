import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';

export const AppShell: React.FC = () => {
  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <TopHeader />
        <main style={{ flex: 1 }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
