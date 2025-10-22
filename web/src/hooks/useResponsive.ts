import { useState, useEffect } from 'react';

export interface BreakpointConfig {
  xs: number;
  sm: number;
  md: number;
  lg: number;
  xl: number;
  xxl: number;
}

export interface ResponsiveState {
  width: number;
  height: number;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  breakpoint: keyof BreakpointConfig;
}

const defaultBreakpoints: BreakpointConfig = {
  xs: 480,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1600,
};

export const useResponsive = (breakpoints: BreakpointConfig = defaultBreakpoints) => {
  const [state, setState] = useState<ResponsiveState>(() => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    return {
      width,
      height,
      isMobile: width < breakpoints.md,
      isTablet: width >= breakpoints.md && width < breakpoints.lg,
      isDesktop: width >= breakpoints.lg,
      breakpoint: getBreakpoint(width, breakpoints),
    };
  });

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    
    const handleResize = () => {
      // 防抖处理，避免频繁触发
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        setState({
          width,
          height,
          isMobile: width < breakpoints.md,
          isTablet: width >= breakpoints.md && width < breakpoints.lg,
          isDesktop: width >= breakpoints.lg,
          breakpoint: getBreakpoint(width, breakpoints),
        });
      }, 100);
    };

    // 监听窗口大小变化
    window.addEventListener('resize', handleResize);
    
    // 监听开发者工具开关（通过窗口大小变化检测）
    window.addEventListener('orientationchange', handleResize);
    
    // 监听可见性变化（可能影响布局）
    document.addEventListener('visibilitychange', handleResize);

    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleResize);
      document.removeEventListener('visibilitychange', handleResize);
    };
  }, [breakpoints]);

  return state;
};

function getBreakpoint(width: number, breakpoints: BreakpointConfig): keyof BreakpointConfig {
  if (width >= breakpoints.xxl) return 'xxl';
  if (width >= breakpoints.xl) return 'xl';
  if (width >= breakpoints.lg) return 'lg';
  if (width >= breakpoints.md) return 'md';
  if (width >= breakpoints.sm) return 'sm';
  return 'xs';
}

// 响应式工具函数
export const responsiveUtils = {
  // 根据断点返回不同的值
  getValue: <T>(values: Partial<Record<keyof BreakpointConfig, T>>, breakpoint: keyof BreakpointConfig, defaultValue: T): T => {
    // 从大到小查找匹配的断点
    const breakpointOrder: (keyof BreakpointConfig)[] = ['xxl', 'xl', 'lg', 'md', 'sm', 'xs'];
    const currentIndex = breakpointOrder.indexOf(breakpoint);
    
    for (let i = currentIndex; i < breakpointOrder.length; i++) {
      const bp = breakpointOrder[i];
      if (values[bp] !== undefined) {
        return values[bp]!;
      }
    }
    
    return defaultValue;
  },
  
  // 生成响应式样式对象
  getResponsiveStyle: (styles: Partial<Record<keyof BreakpointConfig, React.CSSProperties>>, breakpoint: keyof BreakpointConfig): React.CSSProperties => {
    return responsiveUtils.getValue(styles, breakpoint, {});
  },
  
  // 检查是否应该显示某个元素
  shouldShow: (visibility: Partial<Record<keyof BreakpointConfig, boolean>>, breakpoint: keyof BreakpointConfig, defaultValue: boolean = true): boolean => {
    return responsiveUtils.getValue(visibility, breakpoint, defaultValue);
  }
};
