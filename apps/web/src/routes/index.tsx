import { createBrowserRouter, Navigate } from 'react-router-dom';
import Layout from '../components/Layout';
import LoginPage from '../pages/LoginPage';
import DashboardPage from '../pages/DashboardPage';
import ProjectsPage from '../pages/ProjectsPage';
import ProjectDetailPage from '../pages/ProjectDetailPage';
import TestCasesPage from '../pages/TestCasesPage';
import TestFlowsPage from '../pages/TestFlowsPage';
import TestRunsPage from '../pages/TestRunsPage';
import RunDetailPage from '../pages/RunDetailPage';
import DevicesPage from '../pages/DevicesPage';
import PlansPage from '../pages/PlansPage';
import ComparisonPage from '../pages/ComparisonPage';
import PackagesPage from '../pages/PackagesPage';

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('auth-storage');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <Layout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/projects" replace />,
      },
      {
        path: 'packages',
        element: <PackagesPage />,
      },
      {
        path: 'devices',
        element: <DevicesPage />,
      },
      {
        path: 'projects',
        element: <ProjectsPage />,
      },
      {
        path: 'projects/:projectId',
        element: <ProjectDetailPage />,
        children: [
          {
            index: true,
            element: <Navigate to="dashboard" replace />,
          },
          {
            path: 'dashboard',
            element: <DashboardPage />,
          },
          {
            path: 'cases',
            element: <TestCasesPage />,
          },
          {
            path: 'flows',
            element: <TestFlowsPage />,
          },
          {
            path: 'runs',
            element: <TestRunsPage />,
          },
          {
            path: 'runs/:runId',
            element: <RunDetailPage />,
          },
          {
            path: 'plans',
            element: <PlansPage />,
          },
          {
            path: 'comparison',
            element: <ComparisonPage />,
          },
        ],
      },
    ],
  },
]);

export default router;
