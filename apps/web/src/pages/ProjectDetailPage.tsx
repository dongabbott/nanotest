import { useEffect } from 'react';
import { Outlet, NavLink, useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { 
  LayoutDashboard, 
  FileCode, 
  GitBranch, 
  Play,
  Calendar,
  GitCompare,
  ChevronLeft
} from 'lucide-react';
import { projectsApi } from '../services/api';

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { data: project, error, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: async () => {
      const response = await projectsApi.get(projectId!);
      return response.data;
    },
    enabled: !!projectId,
    retry: false,
  });

  useEffect(() => {
    if (error) {
      navigate('/projects', { replace: true });
    }
  }, [error, navigate]);

  const navItems = [
    { to: 'dashboard', icon: LayoutDashboard, label: '仪表盘' },
    { to: 'cases', icon: FileCode, label: '测试用例' },
    { to: 'flows', icon: GitBranch, label: '测试流程' },
    { to: 'runs', icon: Play, label: '执行记录' },
    { to: 'plans', icon: Calendar, label: '测试计划' },
    { to: 'comparison', icon: GitCompare, label: '运行对比' },
  ];

  return (
    <div className="min-h-full">
      {/* Project Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="px-8 py-4">
          <Link 
            to="/projects" 
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ChevronLeft size={16} />
            <span>返回项目列表</span>
          </Link>
          <h1 className="text-xl font-bold text-gray-900">
            {isLoading ? '加载中...' : project?.name || '项目详情'}
          </h1>
        </div>

        {/* Sub Navigation */}
        <div className="px-8">
          <nav className="flex gap-4 overflow-x-auto">
            {navItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-1 py-3 border-b-2 text-sm font-medium transition-colors whitespace-nowrap ${
                    isActive
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`
                }
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </div>

      {/* Page Content */}
      <div className="p-8">
        <Outlet />
      </div>
    </div>
  );
}
