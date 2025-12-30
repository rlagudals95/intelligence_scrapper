
import React, { useMemo } from 'react';
import { Cell, FilterOption, View, PlanGroup, Discount } from '../types';

// --- MiniBarChart Component ---
interface MiniBarChartProps {
  discountMax: Discount;
  discountMin: Discount;
  moyoDiscount: Discount;
}

const MiniBarChart: React.FC<MiniBarChartProps> = ({
  discountMax,
  discountMin,
  moyoDiscount,
}) => {
  const { value: max, source: maxSource } = discountMax;
  const { value: min, source: minSource } = discountMin;
  const { value: moyo, source: moyoSource } = moyoDiscount;

  const range = max - min;
  const moyoPosition = range > 0 ? ((moyo - min) / range) * 100 : 50;
  const clampedPosition = Math.max(0, Math.min(100, moyoPosition));

  const getColorClass = (pos: number) => {
    if (pos <= 30) return 'bg-[#DC1818]';
    if (pos >= 70) return 'bg-[#4096FF]';
    return 'bg-[#D46B08]';
  };

  const getTextColorClass = (pos: number) => {
    if (pos <= 30) return 'text-[#DC1818]';
    if (pos >= 70) return 'text-[#4096FF]';
    return 'text-[#D46B08]';
  };

  const dotColor = getColorClass(clampedPosition);
  const textColor = getTextColorClass(clampedPosition);

  return (
    <div className="w-[340px]">
      {/* 2. 바 + 도트 */}
      <div className="relative h-2 mt-2 mb-6 pt-6">
        {/* 배경 바 */}
        <div className="w-full h-2 bg-gray-300 rounded-full" />
        
        {/* 모요 도트 + 라벨 */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
          style={{ left: `${clampedPosition}%`, top: '28px' /* pt-6(24px) + h-2/2(4px) */ }}
        >
          {/* 화살표 + 금액 라벨 */}
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 flex flex-col items-center">
            {/* 금액 박스 */}
            <div className="px-2 py-1 bg-white rounded border border-gray-300 shadow-sm flex flex-col items-center">
              <span className="text-xs text-gray-500 whitespace-nowrap">{moyoSource}</span>
              <span className={`text-xs font-bold ${textColor} whitespace-nowrap`}>
                {moyo.toLocaleString()}
              </span>
            </div>
            {/* 화살표 */}
            <div
              style={{
                width: 0,
                height: 0,
                borderLeft: '4px solid transparent',
                borderRight: '4px solid transparent',
                borderTop: '4px solid white',
                filter: 'drop-shadow(0 1px 1px rgb(0 0 0 / 0.05))',
                marginTop: '-1px',
              }}
            />
          </div>
          
          {/* 도트 */}
          <div className={`w-3 h-3 ${dotColor} border-2 border-white rounded-full shadow-md z-10`} />
        </div>
      </div>

      {/* 3. 업체명 및 금액 */}
      <div className="flex justify-between text-xs mt-2">
        <div className="text-left">
          <div className="font-medium text-gray-600">{min.toLocaleString()}</div>
          <div className="text-gray-500">{minSource}</div>
        </div>
        <div className="text-right">
          <div className="font-medium text-gray-600">{max.toLocaleString()}</div>
          <div className="text-gray-500">{maxSource}</div>
        </div>
      </div>
    </div>
  );
};


// --- CarrierTable Component ---
interface CarrierTableProps {
  carrier: FilterOption;
  currentView: View | undefined;
}

export const CarrierTable: React.FC<CarrierTableProps> = ({ carrier, currentView }) => {
  const planGroups = useMemo(() => {
    if (!currentView) return {};

    const carrierCells = currentView.cells.filter(cell => cell.carrier === carrier.value);
    
    const groups: { [key: string]: PlanGroup } = {};
    carrierCells.forEach(cell => {
      const key = `${cell.mobile_plan.name}|${cell.mobile_plan.monthly_fee}`;
      if (!groups[key]) {
        groups[key] = {
          plan: cell.mobile_plan,
          device_change: null,
          number_transfer: null
        };
      }
      
      if (cell.mno_join_type === 'DEVICE_CHANGE') {
        groups[key].device_change = cell;
      } else if (cell.mno_join_type === 'NUMBER_TRANSFER') {
        groups[key].number_transfer = cell;
      }
    });
    
    return groups;
  }, [carrier, currentView]);

  const getCarrierBgColor = (carrierValue: string) => {
    switch (carrierValue) {
      case 'SKT':
        return 'bg-[#EA002C]';
      case 'LGU':
        return 'bg-[rgb(230,0,126)]';
      case 'KT':
        return 'bg-[#000000]';
      default:
        return 'bg-gray-50';
    }
  };

  const carrierBg = getCarrierBgColor(carrier.value);
  const headerTextColor = carrier.value === 'SKT' || carrier.value === 'LGU' || carrier.value === 'KT' ? 'text-white' : 'text-gray-900';


  if (!currentView || Object.keys(planGroups).length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden border border-gray-200/80">
      <div className={`${carrierBg} px-6 py-4 border-b border-transparent`}>
        <h2 className={`text-lg font-bold ${headerTextColor}`}>{carrier.label}</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1024px] table-fixed">
          <thead className="bg-gray-100">
            <tr>
              <th scope="col" className="px-6 py-4 text-left text-sm font-bold text-gray-700 w-[240px]">
                요금제
              </th>
              <th scope="col" className="px-6 py-4 text-left text-sm font-bold text-gray-700">
                기기변경
              </th>
              <th scope="col" className="px-6 py-4 text-left text-sm font-bold text-gray-700">
                번호이동
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {Object.values(planGroups)
              .sort((a, b) => b.plan.monthly_fee - a.plan.monthly_fee)
              .map((group) => (
              <tr key={`${group.plan.name}-${group.plan.monthly_fee}`} className="hover:bg-gray-50/50 transition-colors">
                <td className="px-6 py-5 align-top">
                  <div className="font-semibold text-gray-900 truncate" title={group.plan.name}>{group.plan.name}</div>
                  <div className="text-sm text-gray-500 mt-1">
                    월 {group.plan.monthly_fee.toLocaleString()}원
                  </div>
                </td>
                <td className="px-6 py-5 align-top">
                  {group.device_change ? (
                    <MiniBarChart 
                      discountMax={group.device_change.policy_level.discount_max}
                      discountMin={group.device_change.policy_level.discount_min}
                      moyoDiscount={group.device_change.policy_level.moyo_discount}
                    />
                  ) : <span className="text-gray-400 text-sm">-</span>}
                </td>
                <td className="px-6 py-5 align-top">
                  {group.number_transfer ? (
                    <MiniBarChart 
                      discountMax={group.number_transfer.policy_level.discount_max}
                      discountMin={group.number_transfer.policy_level.discount_min}
                      moyoDiscount={group.number_transfer.policy_level.moyo_discount}
                    />
                  ) : <span className="text-gray-400 text-sm">-</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
