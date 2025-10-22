import React from 'react';
import { Card, Typography, Space, Tag, Button } from 'antd';
import { useResponsive } from '../hooks/useResponsive';

const { Title, Text, Paragraph } = Typography;

const ResponsiveTest: React.FC = () => {
  const responsive = useResponsive();

  return (
    <div style={{ padding: '24px', maxWidth: '100%' }}>
      <Title level={2}>响应式布局测试</Title>
      
      <Card style={{ marginBottom: '24px' }}>
        <Title level={3}>当前屏幕信息</Title>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>屏幕尺寸: </Text>
            <Tag color="blue">{responsive.width} x {responsive.height}</Tag>
          </div>
          <div>
            <Text strong>断点: </Text>
            <Tag color="green">{responsive.breakpoint}</Tag>
          </div>
          <div>
            <Text strong>设备类型: </Text>
            <Space>
              <Tag color={responsive.isMobile ? 'red' : 'default'}>
                移动端: {responsive.isMobile ? '是' : '否'}
              </Tag>
              <Tag color={responsive.isTablet ? 'orange' : 'default'}>
                平板: {responsive.isTablet ? '是' : '否'}
              </Tag>
              <Tag color={responsive.isDesktop ? 'green' : 'default'}>
                桌面端: {responsive.isDesktop ? '是' : '否'}
              </Tag>
            </Space>
          </div>
        </Space>
      </Card>

      <Card style={{ marginBottom: '24px' }}>
        <Title level={3}>响应式测试</Title>
        <Paragraph>
          请尝试以下操作来测试响应式功能：
        </Paragraph>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>1. 调整浏览器窗口大小</Text>
            <br />
            <Text type="secondary">观察布局如何自动适应不同的屏幕尺寸</Text>
          </div>
          <div>
            <Text strong>2. 打开/关闭开发者工具</Text>
            <br />
            <Text type="secondary">在右侧打开开发者工具，然后关闭，观察界面是否自动适应</Text>
          </div>
          <div>
            <Text strong>3. 旋转移动设备</Text>
            <br />
            <Text type="secondary">如果在移动设备上，尝试旋转屏幕</Text>
          </div>
          <div>
            <Text strong>4. 使用不同的浏览器</Text>
            <br />
            <Text type="secondary">测试在不同浏览器中的表现</Text>
          </div>
        </Space>
      </Card>

      <Card>
        <Title level={3}>响应式特性</Title>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>✓ 自适应布局</Text>
            <br />
            <Text type="secondary">布局会根据屏幕尺寸自动调整</Text>
          </div>
          <div>
            <Text strong>✓ 移动端优化</Text>
            <br />
            <Text type="secondary">移动端使用抽屉菜单和简化的界面</Text>
          </div>
          <div>
            <Text strong>✓ 开发者工具适配</Text>
            <br />
            <Text type="secondary">自动检测窗口大小变化并重新布局</Text>
          </div>
          <div>
            <Text strong>✓ 防抖处理</Text>
            <br />
            <Text type="secondary">避免频繁的布局重计算，提升性能</Text>
          </div>
          <div>
            <Text strong>✓ 断点系统</Text>
            <br />
            <Text type="secondary">支持 xs, sm, md, lg, xl, xxl 断点</Text>
          </div>
        </Space>
      </Card>

      <div style={{ marginTop: '24px', textAlign: 'center' }}>
        <Button 
          type="primary" 
          size="large"
          onClick={() => window.location.reload()}
        >
          刷新页面测试
        </Button>
      </div>
    </div>
  );
};

export default ResponsiveTest;
