import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X, Loader2 } from 'lucide-react';
import { devicesApi } from '../../services/api';

export function CreateDevicePoolModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      devicesApi.createPool('', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devicePools'] });
      onClose();
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建设备池失败');
    },
  });

  const resetForm = () => {
    setName('');
    setDescription('');
    setError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('请输入设备池名称');
      return;
    }
    createMutation.mutate({ 
      name: name.trim(), 
      description: description.trim() || undefined 
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">创建设备池</h2>
          <button onClick={() => { onClose(); resetForm(); }} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">{error}</div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              设备池名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Android真机池"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              描述
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="用于执行Android测试的设备池"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={() => { onClose(); resetForm(); }}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {createMutation.isPending && <Loader2 size={16} className="animate-spin" />}
              {createMutation.isPending ? '创建中...' : '创建设备池'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DevicePoolSettingsModal({
  isOpen,
  onClose,
  pool,
  onSave,
}: {
  isOpen: boolean;
  onClose: () => void;
  pool: any;
  onSave: (data: any) => void;
}) {
  const [name, setName] = useState(pool?.name || '');
  const [description, setDescription] = useState(pool?.description || '');

  if (!isOpen || !pool) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({ name, description });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">编辑设备池</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">设备池名称</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">描述</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="设备池描述"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              保存
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
