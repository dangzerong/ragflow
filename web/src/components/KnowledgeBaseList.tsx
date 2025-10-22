import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Space, Tag, Card, Empty } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, ReloadOutlined, FolderOutlined } from '@ant-design/icons';
import { knowledgeBaseApi } from '../services/api';
import { useResponsive } from '../hooks/useResponsive';
import type { KnowledgeBase, CreateKnowledgeBaseRequest, UpdateKnowledgeBaseRequest } from '../types/api';

const KnowledgeBaseList: React.FC = () => {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null);
  const [form] = Form.useForm();
  const responsive = useResponsive();

  // 获取知识库列表
  const fetchKbs = async () => {
    setLoading(true);
    try {
      const response = await knowledgeBaseApi.list();
      if (response.code === 0) {
        setKbs(response.data?.kbs || []);
      } else {
        message.error(response.message || '获取知识库列表失败');
      }
    } catch (error) {
      message.error('获取知识库列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKbs();
  }, []);

  // 创建知识库
  const handleCreate = async (values: CreateKnowledgeBaseRequest) => {
    try {
      const response = await knowledgeBaseApi.create(values);
      if (response.code === 0) {
        message.success('创建知识库成功');
        setModalVisible(false);
        form.resetFields();
        fetchKbs();
      } else {
        message.error(response.message || '创建知识库失败');
      }
    } catch (error) {
      message.error('创建知识库失败');
    }
  };

  // 更新知识库
  const handleUpdate = async (values: UpdateKnowledgeBaseRequest) => {
    try {
      const response = await knowledgeBaseApi.update(values);
      if (response.code === 0) {
        message.success('更新知识库成功');
        setModalVisible(false);
        setEditingKb(null);
        form.resetFields();
        fetchKbs();
      } else {
        message.error(response.message || '更新知识库失败');
      }
    } catch (error) {
      message.error('更新知识库失败');
    }
  };

  // 删除知识库
  const handleDelete = async (kb_id: string) => {
    try {
      const response = await knowledgeBaseApi.delete({ kb_id });
      if (response.code === 0) {
        message.success('删除知识库成功');
        fetchKbs();
      } else {
        message.error(response.message || '删除知识库失败');
      }
    } catch (error) {
      message.error('删除知识库失败');
    }
  };

  // 打开创建模态框
  const openCreateModal = () => {
    setEditingKb(null);
    setModalVisible(true);
    form.resetFields();
  };

  // 打开编辑模态框
  const openEditModal = (kb: KnowledgeBase) => {
    setEditingKb(kb);
    setModalVisible(true);
    form.setFieldsValue({
      name: kb.name,
      description: kb.description,
    });
  };

  // 响应式表格列定义
  const getColumns = () => {
    const baseColumns: any[] = [
      {
        title: '名称',
        dataIndex: 'name',
        key: 'name',
        render: (text: string) => (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FolderOutlined style={{ color: '#e91e63' }} />
            <span style={{ fontWeight: '500' }}>{text}</span>
          </div>
        ),
      },
      {
        title: '描述',
        dataIndex: 'description',
        key: 'description',
        ellipsis: true,
        render: (text: string) => text || '-',
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: responsive.isMobile ? 80 : 100,
        render: (status: string) => (
          <Tag color={status === 'active' ? 'green' : 'red'}>
            {status}
          </Tag>
        ),
      },
    ];

    // 桌面端显示更多列
    if (!responsive.isMobile) {
      baseColumns.unshift({
        title: 'ID',
        dataIndex: 'id',
        key: 'id',
        width: 200,
        ellipsis: true,
      });
      
      baseColumns.push(
        {
          title: '文档数量',
          dataIndex: 'document_count',
          key: 'document_count',
          width: 120,
          render: (count: any) => count || 0,
        },
        {
          title: '块数量',
          dataIndex: 'chunk_count',
          key: 'chunk_count',
          width: 120,
          render: (count: any) => count || 0,
        },
        {
          title: '创建时间',
          dataIndex: 'create_time',
          key: 'create_time',
          width: 180,
          render: (time: string) => time ? new Date(time).toLocaleString() : '-',
        }
      );
    }

    // 操作列
    baseColumns.push({
      title: '操作',
      key: 'action',
      width: responsive.isMobile ? 120 : 150,
      fixed: responsive.isMobile ? 'right' : undefined,
      render: (_: any, record: KnowledgeBase) => (
        <Space direction={responsive.isMobile ? 'vertical' : 'horizontal'} size="small">
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
            style={{ color: '#e91e63', padding: responsive.isMobile ? '4px 8px' : undefined }}
            size={responsive.isMobile ? 'small' : 'middle'}
          >
            {responsive.isMobile ? '' : '编辑'}
          </Button>
          <Popconfirm
            title="确定要删除这个知识库吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              size={responsive.isMobile ? 'small' : 'middle'}
              style={{ padding: responsive.isMobile ? '4px 8px' : undefined }}
            >
              {responsive.isMobile ? '' : '删除'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    });

    return baseColumns;
  };

  return (
    <div style={{ width: '100%', maxWidth: '100%' }}>
      {/* 页面标题和操作栏 */}
      <div style={{ 
        marginBottom: responsive.isMobile ? '16px' : '24px',
        display: 'flex',
        flexDirection: responsive.isMobile ? 'column' : 'row',
        justifyContent: 'space-between',
        alignItems: responsive.isMobile ? 'stretch' : 'center',
        gap: responsive.isMobile ? '12px' : '0'
      }}>
        <div>
          <h1 style={{ 
            margin: 0, 
            fontSize: responsive.isMobile ? '20px' : '24px',
            fontWeight: '600',
            color: '#333'
          }}>
            知识库管理
          </h1>
        </div>
        
        <div style={{ 
          display: 'flex', 
          gap: '12px',
          flexDirection: responsive.isMobile ? 'row' : 'row',
          justifyContent: responsive.isMobile ? 'stretch' : 'flex-end'
        }}>
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchKbs}
            loading={loading}
            size={responsive.isMobile ? 'small' : 'middle'}
            style={{ flex: responsive.isMobile ? 1 : 'none' }}
          >
            {responsive.isMobile ? '' : '刷新'}
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreateModal}
            size={responsive.isMobile ? 'small' : 'middle'}
            style={{
              background: '#e91e63',
              borderColor: '#e91e63',
              flex: responsive.isMobile ? 1 : 'none'
            }}
          >
            {responsive.isMobile ? '新建' : '新建知识库'}
          </Button>
        </div>
      </div>

      {/* 搜索和筛选区域 - 桌面端显示 */}
      {!responsive.isMobile && (
        <Card style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <Input
              placeholder="搜索知识库..."
              prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
              style={{ width: '300px' }}
              allowClear
            />
            <Input
              placeholder="团队筛选"
              style={{ width: '150px' }}
              defaultValue="全部"
            />
            <Button icon={<ReloadOutlined />}>
              刷新
            </Button>
          </div>
        </Card>
      )}

      {/* 知识库列表 */}
      {kbs.length === 0 ? (
        <Card>
          <Empty
            image={<FolderOutlined style={{ fontSize: responsive.isMobile ? '48px' : '64px', color: '#d9d9d9' }} />}
            description={
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: responsive.isMobile ? '14px' : '16px', color: '#666', marginBottom: '8px' }}>
                  暂无知识库
                </div>
                <div style={{ fontSize: responsive.isMobile ? '12px' : '14px', color: '#999', marginBottom: '24px' }}>
                  创建您的第一个知识库开始使用
                </div>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={openCreateModal}
                  size={responsive.isMobile ? 'middle' : 'large'}
                  style={{
                    background: '#e91e63',
                    borderColor: '#e91e63'
                  }}
                >
                  新建知识库
                </Button>
              </div>
            }
          />
        </Card>
      ) : (
        <Card>
          <Table
            columns={getColumns()}
            dataSource={kbs}
            loading={loading}
            rowKey="id"
            scroll={responsive.isMobile ? { x: 600 } : undefined}
            pagination={{
              pageSize: responsive.isMobile ? 5 : 10,
              showSizeChanger: !responsive.isMobile,
              showQuickJumper: !responsive.isMobile,
              showTotal: (total) => `共 ${total} 条记录`,
              style: { marginTop: '16px' },
              size: responsive.isMobile ? 'small' : 'default'
            }}
            size={responsive.isMobile ? 'small' : 'middle'}
          />
        </Card>
      )}

      {/* 创建/编辑知识库模态框 */}
      <Modal
        title={editingKb ? '编辑知识库' : '创建知识库'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingKb(null);
          form.resetFields();
        }}
        footer={null}
        width={responsive.isMobile ? '90%' : 600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={editingKb ? handleUpdate : handleCreate as any}
          style={{ marginTop: '24px' }}
        >
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[{ required: true, message: '请输入知识库名称' }]}
          >
            <Input placeholder="请输入知识库名称" size="large" />
          </Form.Item>

          <Form.Item
            name="description"
            label="描述"
          >
            <Input.TextArea 
              placeholder="请输入描述" 
              rows={4} 
              size="large"
            />
          </Form.Item>

          {editingKb && (
            <Form.Item name="kb_id" initialValue={editingKb.id} style={{ display: 'none' }}>
              <Input />
            </Form.Item>
          )}

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setModalVisible(false)} size="large">
                取消
              </Button>
              <Button 
                type="primary" 
                htmlType="submit" 
                size="large"
                style={{
                  background: '#e91e63',
                  borderColor: '#e91e63'
                }}
              >
                {editingKb ? '更新' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default KnowledgeBaseList;