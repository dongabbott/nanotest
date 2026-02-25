import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Package,
  Upload,
  Download,
  Trash2,
  Search,
  MoreHorizontal,
  X,
  Loader2,
  AlertTriangle,
  FileArchive,
  Apple,
  Bot,
  Tag,
  Calendar,
  HardDrive,
  Hash,
  Shield,
  Eye,
  Copy,
  Check,
  RefreshCw,
} from 'lucide-react';
import { packagesApi, projectsApi } from '../services/api';

interface AppPackage {
  id: string;
  project_id: string;
  filename: string;
  platform: 'android' | 'ios';
  package_name: string;
  app_name?: string;
  version_name: string;
  version_code?: number;
  build_number?: string;
  file_size: number;
  file_hash: string;
  min_sdk_version?: number;
  target_sdk_version?: number;
  app_activity?: string;
  app_package?: string;
  bundle_id?: string;
  minimum_os_version?: string;
  supported_platforms?: string[];
  permissions?: string[];
  icon_object_key?: string;
  extra_metadata: Record<string, unknown>;
  status: string;
  description?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function UploadModal({
  isOpen,
  onClose,
  projects,
}: {
  isOpen: boolean;
  onClose: () => void;
  projects: { id: string; name: string }[];
}) {
  const queryClient = useQueryClient();
  const [selectedProject, setSelectedProject] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [dragActive, setDragActive] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file || !selectedProject) throw new Error('请选择项目和文件');
      const tagList = tags.split(',').map(t => t.trim()).filter(Boolean);
      return packagesApi.upload(selectedProject, file, description || undefined, tagList.length > 0 ? tagList : undefined);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      onClose();
      resetForm();
    },
  });

  const resetForm = () => {
    setSelectedProject('');
    setFile(null);
    setDescription('');
    setTags('');
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.name.endsWith('.apk') || droppedFile.name.endsWith('.ipa'))) {
      setFile(droppedFile);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) setFile(selectedFile);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">上传应用包</h2>
          <button onClick={() => { onClose(); resetForm(); }} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>
        <div className="p-6 space-y-4">
          {uploadMutation.isError && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
              <AlertTriangle size={16} />
              {(uploadMutation.error as Error)?.message || '上传失败'}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">选择项目 <span className="text-red-500">*</span></label>
            <select value={selectedProject} onChange={(e) => setSelectedProject(e.target.value)} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
              <option value="">请选择项目</option>
              {projects.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">应用包文件 <span className="text-red-500">*</span></label>
            <div onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop} className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}`}>
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <FileArchive size={24} className="text-blue-600" />
                  <div className="text-left">
                    <p className="font-medium text-gray-900">{file.name}</p>
                    <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
                  </div>
                  <button onClick={() => setFile(null)} className="p-1 hover:bg-gray-100 rounded"><X size={16} className="text-gray-400" /></button>
                </div>
              ) : (
                <>
                  <Upload size={32} className="mx-auto text-gray-400 mb-2" />
                  <p className="text-gray-600 mb-1">拖拽 APK 或 IPA 文件到此处</p>
                  <p className="text-sm text-gray-400 mb-3">或者点击选择文件</p>
                  <input type="file" accept=".apk,.ipa" onChange={handleFileSelect} className="hidden" id="file-upload" />
                  <label htmlFor="file-upload" className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer">选择文件</label>
                </>
              )}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">描述</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="可选的版本说明..." />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">标签</label>
            <input type="text" value={tags} onChange={(e) => setTags(e.target.value)} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="用逗号分隔，如：release, v2.0, 稳定版" />
          </div>
          {uploadMutation.isPending && (
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="flex items-center gap-3 mb-2">
                <Loader2 size={18} className="animate-spin text-blue-600" />
                <span className="text-sm text-blue-700">正在上传并解析包信息...</span>
              </div>
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button onClick={() => { onClose(); resetForm(); }} className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">取消</button>
            <button onClick={() => uploadMutation.mutate()} disabled={!file || !selectedProject || uploadMutation.isPending} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2">
              {uploadMutation.isPending ? (<><Loader2 size={16} className="animate-spin" />上传中...</>) : (<><Upload size={16} />上传</>)}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PackageDetailModal({ isOpen, onClose, pkg }: { isOpen: boolean; onClose: () => void; pkg: AppPackage | null }) {
  const [copied, setCopied] = useState<string | null>(null);
  const copyToClipboard = async (text: string, field: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };
  if (!isOpen || !pkg) return null;
  const PlatformIcon = pkg.platform === 'ios' ? Apple : Bot;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">包详情</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
          <div className="flex items-start gap-4 mb-6">
            <div className={`w-16 h-16 rounded-xl flex items-center justify-center ${pkg.platform === 'ios' ? 'bg-gray-100' : 'bg-green-100'}`}>
              <PlatformIcon size={32} className={pkg.platform === 'ios' ? 'text-gray-700' : 'text-green-700'} />
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-bold text-gray-900">{pkg.app_name || pkg.package_name}</h3>
              <p className="text-gray-500">{pkg.filename}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${pkg.platform === 'ios' ? 'bg-gray-100 text-gray-700' : 'bg-green-100 text-green-700'}`}>{pkg.platform === 'ios' ? 'iOS' : 'Android'}</span>
                <span className="text-sm text-gray-500">v{pkg.version_name}</span>
              </div>
            </div>
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-start gap-2"><Package size={16} className="text-gray-400 mt-0.5" /><div><span className="text-xs text-gray-500">包名</span><div className="text-sm text-gray-900">{pkg.package_name}</div></div></div>
              <div className="flex items-start gap-2"><HardDrive size={16} className="text-gray-400 mt-0.5" /><div><span className="text-xs text-gray-500">文件大小</span><div className="text-sm text-gray-900">{formatFileSize(pkg.file_size)}</div></div></div>
              <div className="flex items-start gap-2"><Hash size={16} className="text-gray-400 mt-0.5" /><div><span className="text-xs text-gray-500">文件哈希</span><div className="text-sm text-gray-900">{pkg.file_hash.substring(0, 16)}...</div></div></div>
              <div className="flex items-start gap-2"><Calendar size={16} className="text-gray-400 mt-0.5" /><div><span className="text-xs text-gray-500">上传时间</span><div className="text-sm text-gray-900">{formatDate(pkg.created_at)}</div></div></div>
            </div>
            {pkg.platform === 'android' && (
              <div className="bg-green-50 rounded-lg p-4">
                <h4 className="font-medium text-green-900 mb-3 flex items-center gap-2"><Bot size={16} />Android 信息</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {pkg.app_activity && (<div><span className="text-green-700">App Activity:</span><div className="font-mono text-green-900 text-xs bg-green-100 px-2 py-1 rounded mt-1">{pkg.app_activity}</div></div>)}
                  {pkg.min_sdk_version && (<div><span className="text-green-700">最低 SDK:</span><span className="ml-2 text-green-900">API {pkg.min_sdk_version}</span></div>)}
                  {pkg.target_sdk_version && (<div><span className="text-green-700">目标 SDK:</span><span className="ml-2 text-green-900">API {pkg.target_sdk_version}</span></div>)}
                </div>
              </div>
            )}
            {pkg.platform === 'ios' && (
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2"><Apple size={16} />iOS 信息</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {pkg.bundle_id && (<div><span className="text-gray-600">Bundle ID:</span><div className="font-mono text-gray-900 text-xs bg-gray-100 px-2 py-1 rounded mt-1">{pkg.bundle_id}</div></div>)}
                  {pkg.minimum_os_version && (<div><span className="text-gray-600">最低 iOS 版本:</span><span className="ml-2 text-gray-900">{pkg.minimum_os_version}</span></div>)}
                </div>
              </div>
            )}
            {pkg.permissions && pkg.permissions.length > 0 && (
              <div className="bg-yellow-50 rounded-lg p-4">
                <h4 className="font-medium text-yellow-900 mb-3 flex items-center gap-2"><Shield size={16} />权限 ({pkg.permissions.length})</h4>
                <div className="flex flex-wrap gap-2">
                  {pkg.permissions.slice(0, 10).map((perm, i) => (<span key={i} className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">{perm.replace('android.permission.', '')}</span>))}
                  {pkg.permissions.length > 10 && <span className="text-xs text-yellow-600">+{pkg.permissions.length - 10} more</span>}
                </div>
              </div>
            )}
            {pkg.tags && pkg.tags.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-700 mb-2 flex items-center gap-2"><Tag size={16} />标签</h4>
                <div className="flex flex-wrap gap-2">{pkg.tags.map((tag, i) => (<span key={i} className="text-sm bg-blue-100 text-blue-700 px-3 py-1 rounded-full">{tag}</span>))}</div>
              </div>
            )}
            {pkg.description && (<div><h4 className="font-medium text-gray-700 mb-2">描述</h4><p className="text-gray-600 text-sm">{pkg.description}</p></div>)}
          </div>
        </div>
      </div>
    </div>
  );
}

function PackageCard({ pkg, onView, onDownload, onDelete }: { pkg: AppPackage; onView: () => void; onDownload: () => void; onDelete: () => void }) {
  const [showMenu, setShowMenu] = useState(false);
  const PlatformIcon = pkg.platform === 'ios' ? Apple : Bot;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${pkg.platform === 'ios' ? 'bg-gray-100' : 'bg-green-100'}`}>
          <PlatformIcon size={24} className={pkg.platform === 'ios' ? 'text-gray-700' : 'text-green-700'} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{pkg.app_name || pkg.package_name}</h3>
            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${pkg.platform === 'ios' ? 'bg-gray-100 text-gray-700' : 'bg-green-100 text-green-700'}`}>{pkg.platform === 'ios' ? 'iOS' : 'Android'}</span>
          </div>
          <div className="mt-1 text-sm text-gray-500 truncate">{pkg.package_name}</div>
          <div className="mt-2 flex items-center gap-4 text-xs text-gray-400">
            <span>v{pkg.version_name}</span>
            <span>{formatFileSize(pkg.file_size)}</span>
            <span>{formatDate(pkg.created_at)}</span>
          </div>
          {pkg.tags && pkg.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {pkg.tags.slice(0, 3).map((tag, i) => (<span key={i} className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded">{tag}</span>))}
              {pkg.tags.length > 3 && <span className="text-xs text-gray-400">+{pkg.tags.length - 3}</span>}
            </div>
          )}
        </div>
        <div className="relative">
          <button onClick={() => setShowMenu(!showMenu)} className="p-2 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600"><MoreHorizontal size={18} /></button>
          {showMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
              <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 w-36">
                <button onClick={() => { onView(); setShowMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"><Eye size={14} />查看详情</button>
                <button onClick={() => { onDownload(); setShowMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"><Download size={14} />下载</button>
                <hr className="my-1" />
                <button onClick={() => { onDelete(); setShowMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-2"><Trash2 size={14} />删除</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PackagesPage() {
  const queryClient = useQueryClient();
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedPackage, setSelectedPackage] = useState<AppPackage | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [platformFilter, setPlatformFilter] = useState<string>('');
  const [page, setPage] = useState(1);

  const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: () => projectsApi.list() });
  const { data: packagesData, isLoading, refetch } = useQuery({
    queryKey: ['packages', platformFilter, page],
    queryFn: () => packagesApi.list({ platform: platformFilter || undefined, page, page_size: 20 }),
  });

  const deleteMutation = useMutation({
    mutationFn: (packageId: string) => packagesApi.delete(packageId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['packages'] }),
  });

  const handleDownload = async (pkg: AppPackage) => {
    try {
      const response = await packagesApi.getDownloadUrl(pkg.id);
      if (response.data?.download_url) window.open(response.data.download_url, '_blank');
    } catch (error) {
      console.error('获取下载链接失败', error);
    }
  };

  const handleDelete = (pkg: AppPackage) => {
    if (confirm(`确定要删除 "${pkg.app_name || pkg.filename}" 吗？`)) deleteMutation.mutate(pkg.id);
  };

  const projects = projectsData?.data?.items || [];
  const packages: AppPackage[] = packagesData?.data?.items || [];
  const total = packagesData?.data?.total || 0;

  const filteredPackages = packages.filter(pkg => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return pkg.package_name.toLowerCase().includes(query) || pkg.app_name?.toLowerCase().includes(query) || pkg.filename.toLowerCase().includes(query);
  });

  const androidCount = packages.filter(p => p.platform === 'android').length;
  const iosCount = packages.filter(p => p.platform === 'ios').length;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 sticky top-16 z-40">
        <div className="px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">包管理</h1>
              <p className="text-sm text-gray-500 mt-1">管理 Android APK 和 iOS IPA 应用包</p>
            </div>
            <button onClick={() => setIsUploadOpen(true)} className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
              <Upload size={18} />上传应用包
            </button>
          </div>
        </div>
      </div>

      <div className="p-8">
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center"><Package size={20} className="text-blue-600" /></div>
              <div><div className="text-2xl font-bold text-gray-900">{total}</div><div className="text-sm text-gray-500">总包数</div></div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center"><Bot size={20} className="text-green-600" /></div>
              <div><div className="text-2xl font-bold text-gray-900">{androidCount}</div><div className="text-sm text-gray-500">Android APK</div></div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center"><Apple size={20} className="text-gray-700" /></div>
              <div><div className="text-2xl font-bold text-gray-900">{iosCount}</div><div className="text-sm text-gray-500">iOS IPA</div></div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center"><HardDrive size={20} className="text-purple-600" /></div>
              <div><div className="text-2xl font-bold text-gray-900">{formatFileSize(packages.reduce((sum, p) => sum + p.file_size, 0))}</div><div className="text-sm text-gray-500">总大小</div></div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 mb-6">
          <div className="flex-1 relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="搜索包名、应用名..." className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
          </div>
          <select value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)} className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
            <option value="">全部平台</option>
            <option value="android">Android</option>
            <option value="ios">iOS</option>
          </select>
          <button onClick={() => refetch()} className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50"><RefreshCw size={18} className="text-gray-500" /></button>
        </div>

        {isLoading ? (
          <div className="space-y-4">{[1, 2, 3].map((i) => (<div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />))}</div>
        ) : filteredPackages.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
            <Package size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">{searchQuery || platformFilter ? '没有找到匹配的包' : '暂无应用包'}</h3>
            <p className="text-gray-500 mb-6 max-w-md mx-auto">{searchQuery || platformFilter ? '尝试修改搜索条件' : '上传 Android APK 或 iOS IPA 文件开始管理您的应用包'}</p>
            {!searchQuery && !platformFilter && (<button onClick={() => setIsUploadOpen(true)} className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">上传应用包</button>)}
          </div>
        ) : (
          <div className="space-y-3">{filteredPackages.map((pkg) => (<PackageCard key={pkg.id} pkg={pkg} onView={() => setSelectedPackage(pkg)} onDownload={() => handleDownload(pkg)} onDelete={() => handleDelete(pkg)} />))}</div>
        )}

        {total > 20 && (
          <div className="mt-6 flex items-center justify-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">上一页</button>
            <span className="text-sm text-gray-500">第 {page} 页，共 {Math.ceil(total / 20)} 页</span>
            <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 20)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">下一页</button>
          </div>
        )}
      </div>

      <UploadModal isOpen={isUploadOpen} onClose={() => setIsUploadOpen(false)} projects={projects} />
      <PackageDetailModal isOpen={!!selectedPackage} onClose={() => setSelectedPackage(null)} pkg={selectedPackage} />
    </div>
  );
}
