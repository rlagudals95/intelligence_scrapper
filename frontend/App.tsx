
import React, { useState, useMemo } from 'react';
import { DashboardData, RawCapture, FlattenedRow } from './types';
import { CarrierTable } from './components/Dashboard';

const DEFAULT_DATA: DashboardData = {
  captured_at: "2025-12-30T12:00:00+09:00",
  filters: {
    sku_codes: [
      { value: "갤럭시 S25", label: "갤럭시 S25" },
      { value: "아이폰 17", label: "아이폰 17" }
    ],
    carriers: [
      { value: "SKT", label: "SKT" },
      { value: "KT", label: "KT" },
      { value: "LGU", label: "LG U+" }
    ]
  },
  views: [
    {
      sku_code: "갤럭시 S25",
      cells: [
        { cell_key: "SKT|DEVICE_CHANGE|5GX 프라임|89000", carrier: "SKT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5GX 프라임", monthly_fee: 89000 }, policy_level: { discount_max: { value: 320000, source: "폰슐랭샵" }, discount_min: { value: 210000, source: "JS컴" }, moyo_discount: { value: 270000, source: "포피플" } } },
        { cell_key: "SKT|DEVICE_CHANGE|5GX 레귤러플러스|79000", carrier: "SKT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5GX 레귤러플러스", monthly_fee: 79000 }, policy_level: { discount_max: { value: 300000, source: "휴대폰천국" }, discount_min: { value: 190000, source: "테크딜러" }, moyo_discount: { value: 240000, source: "포피플" } } },
        { cell_key: "SKT|DEVICE_CHANGE|5GX 레귤러|69000", carrier: "SKT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5GX 레귤러", monthly_fee: 69000 }, policy_level: { discount_max: { value: 270000, source: "JS컴" }, discount_min: { value: 170000, source: "폰슐랭샵" }, moyo_discount: { value: 210000, source: "포피플" } } },
        { cell_key: "SKT|NUMBER_TRANSFER|5GX 프라임|89000", carrier: "SKT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5GX 프라임", monthly_fee: 89000 }, policy_level: { discount_max: { value: 350000, source: "폰슐랭샵" }, discount_min: { value: 260000, source: "휴대폰천국" }, moyo_discount: { value: 310000, source: "포피플" } } },
        { cell_key: "SKT|NUMBER_TRANSFER|5GX 레귤러플러스|79000", carrier: "SKT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5GX 레귤러플러스", monthly_fee: 79000 }, policy_level: { discount_max: { value: 330000, source: "테크딜러" }, discount_min: { value: 240000, source: "JS컴" }, moyo_discount: { value: 290000, source: "포피플" } } },
        { cell_key: "SKT|NUMBER_TRANSFER|5GX 레귤러|69000", carrier: "SKT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5GX 레귤러", monthly_fee: 69000 }, policy_level: { discount_max: { value: 310000, source: "휴대폰천국" }, discount_min: { value: 220000, source: "폰슐랭샵" }, moyo_discount: { value: 260000, source: "포피플" } } },
        { cell_key: "KT|DEVICE_CHANGE|스페셜|100000", carrier: "KT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "스페셜", monthly_fee: 100000 }, policy_level: { discount_max: { value: 310000, source: "폰슐랭샵" }, discount_min: { value: 200000, source: "KT딜샵" }, moyo_discount: { value: 250000, source: "포피플" } } },
        { cell_key: "KT|DEVICE_CHANGE|베이직|80000", carrier: "KT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "베이직", monthly_fee: 80000 }, policy_level: { discount_max: { value: 280000, source: "테크딜러" }, discount_min: { value: 175000, source: "JS컴" }, moyo_discount: { value: 220000, source: "포피플" } } },
        { cell_key: "KT|DEVICE_CHANGE|5G 심플 30GB|61000", carrier: "KT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5G 심플 30GB", monthly_fee: 61000 }, policy_level: { discount_max: { value: 250000, source: "휴대폰천국" }, discount_min: { value: 160000, source: "KT딜샵" }, moyo_discount: { value: 200000, source: "포피플" } } },
        { cell_key: "KT|NUMBER_TRANSFER|스페셜|100000", carrier: "KT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "스페셜", monthly_fee: 100000 }, policy_level: { discount_max: { value: 340000, source: "폰슐랭샵" }, discount_min: { value: 255000, source: "휴대폰천국" }, moyo_discount: { value: 300000, source: "포피플" } } },
        { cell_key: "KT|NUMBER_TRANSFER|베이직|80000", carrier: "KT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "베이직", monthly_fee: 80000 }, policy_level: { discount_max: { value: 320000, source: "KT딜샵" }, discount_min: { value: 230000, source: "테크딜러" }, moyo_discount: { value: 270000, source: "포피플" } } },
        { cell_key: "KT|NUMBER_TRANSFER|5G 심플 30GB|61000", carrier: "KT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5G 심플 30GB", monthly_fee: 61000 }, policy_level: { discount_max: { value: 290000, source: "JS컴" }, discount_min: { value: 205000, source: "KT딜샵" }, moyo_discount: { value: 245000, source: "포피플" } } },
        { cell_key: "LGU|DEVICE_CHANGE|5G 프리미어 에센셜|85000", carrier: "LGU", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5G 프리미어 에센셜", monthly_fee: 85000 }, policy_level: { discount_max: { value: 295000, source: "폰슐랭샵" }, discount_min: { value: 185000, source: "U+딜스팟" }, moyo_discount: { value: 230000, source: "포피플" } } },
        { cell_key: "LGU|DEVICE_CHANGE|5G 심플+|61000", carrier: "LGU", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5G 심플+", monthly_fee: 61000 }, policy_level: { discount_max: { value: 260000, source: "테크딜러" }, discount_min: { value: 155000, source: "JS컴" }, moyo_discount: { value: 200000, source: "포피플" } } },
        { cell_key: "LGU|NUMBER_TRANSFER|5G 프리미어 에센셜|85000", carrier: "LGU", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5G 프리미어 에센셜", monthly_fee: 85000 }, policy_level: { discount_max: { value: 325000, source: "U+딜스팟" }, discount_min: { value: 240000, source: "휴대폰천국" }, moyo_discount: { value: 285000, source: "포피플" } } },
        { cell_key: "LGU|NUMBER_TRANSFER|5G 심플+|61000", carrier: "LGU", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5G 심플+", monthly_fee: 61000 }, policy_level: { discount_max: { value: 285000, source: "폰슐랭샵" }, discount_min: { value: 210000, source: "U+딜스팟" }, moyo_discount: { value: 250000, source: "포피플" } } }
      ]
    },
    {
      sku_code: "아이폰 17",
      cells: [
        { cell_key: "SKT|DEVICE_CHANGE|5GX 프라임|89000", carrier: "SKT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5GX 프라임", monthly_fee: 89000 }, policy_level: { discount_max: { value: 305000, source: "테크딜러" }, discount_min: { value: 195000, source: "JS컴" }, moyo_discount: { value: 245000, source: "포피플" } } },
        { cell_key: "SKT|DEVICE_CHANGE|5GX 레귤러플러스|79000", carrier: "SKT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5GX 레귤러플러스", monthly_fee: 79000 }, policy_level: { discount_max: { value: 285000, source: "폰슐랭샵" }, discount_min: { value: 180000, source: "휴대폰천국" }, moyo_discount: { value: 225000, source: "포피플" } } },
        { cell_key: "SKT|DEVICE_CHANGE|5GX 레귤러|69000", carrier: "SKT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5GX 레귤러", monthly_fee: 69000 }, policy_level: { discount_max: { value: 260000, source: "JS컴" }, discount_min: { value: 165000, source: "폰슐랭샵" }, moyo_discount: { value: 205000, source: "포피플" } } },
        { cell_key: "SKT|NUMBER_TRANSFER|5GX 프라임|89000", carrier: "SKT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5GX 프라임", monthly_fee: 89000 }, policy_level: { discount_max: { value: 335000, source: "휴대폰천국" }, discount_min: { value: 250000, source: "테크딜러" }, moyo_discount: { value: 295000, source: "포피플" } } },
        { cell_key: "SKT|NUMBER_TRANSFER|5GX 레귤러플러스|79000", carrier: "SKT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5GX 레귤러플러스", monthly_fee: 79000 }, policy_level: { discount_max: { value: 315000, source: "폰슐랭샵" }, discount_min: { value: 235000, source: "JS컴" }, moyo_discount: { value: 275000, source: "포피플" } } },
        { cell_key: "SKT|NUMBER_TRANSFER|5GX 레귤러|69000", carrier: "SKT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5GX 레귤러", monthly_fee: 69000 }, policy_level: { discount_max: { value: 295000, source: "테크딜러" }, discount_min: { value: 215000, source: "휴대폰천국" }, moyo_discount: { value: 255000, source: "포피플" } } },
        { cell_key: "KT|DEVICE_CHANGE|스페셜|100000", carrier: "KT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "스페셜", monthly_fee: 100000 }, policy_level: { discount_max: { value: 300000, source: "KT딜샵" }, discount_min: { value: 195000, source: "JS컴" }, moyo_discount: { value: 240000, source: "포피플" } } },
        { cell_key: "KT|DEVICE_CHANGE|베이직|80000", carrier: "KT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "베이직", monthly_fee: 80000 }, policy_level: { discount_max: { value: 270000, source: "폰슐랭샵" }, discount_min: { value: 170000, source: "KT딜샵" }, moyo_discount: { value: 215000, source: "포피플" } } },
        { cell_key: "KT|DEVICE_CHANGE|5G 심플 30GB|61000", carrier: "KT", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5G 심플 30GB", monthly_fee: 61000 }, policy_level: { discount_max: { value: 245000, source: "테크딜러" }, discount_min: { value: 155000, source: "JS컴" }, moyo_discount: { value: 195000, source: "포피플" } } },
        { cell_key: "KT|NUMBER_TRANSFER|스페셜|100000", carrier: "KT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "스페셜", monthly_fee: 100000 }, policy_level: { discount_max: { value: 330000, source: "휴대폰천국" }, discount_min: { value: 245000, source: "KT딜샵" }, moyo_discount: { value: 290000, source: "포피플" } } },
        { cell_key: "KT|NUMBER_TRANSFER|베이직|80000", carrier: "KT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "베이직", monthly_fee: 80000 }, policy_level: { discount_max: { value: 310000, source: "폰슐랭샵" }, discount_min: { value: 225000, source: "테크딜러" }, moyo_discount: { value: 265000, source: "포피플" } } },
        { cell_key: "KT|NUMBER_TRANSFER|5G 심플 30GB|61000", carrier: "KT", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5G 심플 30GB", monthly_fee: 61000 }, policy_level: { discount_max: { value: 285000, source: "KT딜샵" }, discount_min: { value: 205000, source: "JS컴" }, moyo_discount: { value: 245000, source: "포피플" } } },
        { cell_key: "LGU|DEVICE_CHANGE|5G 프리미어 에센셜|85000", carrier: "LGU", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5G 프리미어 에센셜", monthly_fee: 85000 }, policy_level: { discount_max: { value: 290000, source: "U+딜스팟" }, discount_min: { value: 185000, source: "JS컴" }, moyo_discount: { value: 225000, source: "포피플" } } },
        { cell_key: "LGU|DEVICE_CHANGE|5G 심플+|61000", carrier: "LGU", mno_join_type: "DEVICE_CHANGE", mobile_plan: { name: "5G 심플+", monthly_fee: 61000 }, policy_level: { discount_max: { value: 255000, source: "폰슐랭샵" }, discount_min: { value: 150000, source: "U+딜스팟" }, moyo_discount: { value: 195000, source: "포피플" } } },
        { cell_key: "LGU|NUMBER_TRANSFER|5G 프리미어 에센셜|85000", carrier: "LGU", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5G 프리미어 에센셜", monthly_fee: 85000 }, policy_level: { discount_max: { value: 320000, source: "휴대폰천국" }, discount_min: { value: 235000, source: "U+딜스팟" }, moyo_discount: { value: 280000, source: "포피플" } } },
        { cell_key: "LGU|NUMBER_TRANSFER|5G 심플+|61000", carrier: "LGU", mno_join_type: "NUMBER_TRANSFER", mobile_plan: { name: "5G 심플+", monthly_fee: 61000 }, policy_level: { discount_max: { value: 280000, source: "테크딜러" }, discount_min: { value: 205000, source: "JS컴" }, moyo_discount: { value: 245000, source: "포피플" } } }
      ]
    }
  ]
};

const App: React.FC = () => {
  const [data, setData] = useState<DashboardData>(DEFAULT_DATA);
  const [fileName, setFileName] = useState<string>("샘플 데이터");
  const [selectedSku, setSelectedSku] = useState<string>(data.filters.sku_codes[0].value);
  const [activeTab, setActiveTab] = useState<string>("table");
  const [rawData, setRawData] = useState<RawCapture[] | null>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.json')) {
      alert('JSON 파일만 업로드 가능합니다.');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const result = e.target?.result;
        if (typeof result !== 'string') {
          throw new Error('파일을 읽을 수 없습니다.');
        }
        const jsonData = JSON.parse(result);
        
        if (Array.isArray(jsonData)) {
          setRawData(jsonData);
          alert('Raw 데이터 로드 성공! Raw 데이터 탭에서 확인하세요.');
          setActiveTab('raw');
        } else if (jsonData.filters && jsonData.views) {
          setData(jsonData);
          setFileName(file.name);
          if (jsonData.filters.sku_codes.length > 0) {
            setSelectedSku(jsonData.filters.sku_codes[0].value);
          }
          alert('데이터 로드 성공!');
        } else {
          throw new Error('올바른 형식이 아닙니다.');
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : '알 수 없는 오류';
        alert(`파일 처리 중 오류가 발생했습니다: ${message}`);
      }
    };
    reader.onerror = () => {
      alert('파일 읽기에 실패했습니다.');
    };
    reader.readAsText(file);
    event.target.value = '';
  };

  const handleReset = () => {
    setData(DEFAULT_DATA);
    setFileName("샘플 데이터");
    setRawData(null);
    setSelectedSku(DEFAULT_DATA.filters.sku_codes[0].value);
    setActiveTab('table');
    alert('초기 데이터로 복원되었습니다.');
  };

  const flattenedData = useMemo((): FlattenedRow[] => {
    if (!rawData) return [];
    
    const flattened: FlattenedRow[] = [];
    
    rawData.forEach(capture => {
      const site = capture.source.site;
      const capturedAt = new Date(capture.captured_at).toLocaleString('ko-KR');
      
      capture.products.forEach(product => {
        const skuCode = product.sku_code;
        const storage = product.sku_storage;
        
        product.policies.forEach(policy => {
          flattened.push({
            site,
            capturedAt,
            skuCode,
            storage,
            carrier: policy.carrier,
            joinType: policy.mno_join_type === 'DEVICE_CHANGE' ? '기기변경' : '번호이동',
            planName: policy.mobile_plan.name,
            monthlyFee: policy.mobile_plan.monthly_fee.toLocaleString(),
            retailPrice: policy.pricing.mno_retail_price.toLocaleString(),
            publicSubsidy: policy.pricing.public_subsidy.toLocaleString(),
            discount: policy.pricing.discount.toLocaleString(),
            installmentFee: policy.pricing.sku_installment_fee.toLocaleString()
          });
        });
      });
    });
    
    return flattened;
  }, [rawData]);

  const handleDownloadCsv = () => {
    const headers = ['사이트', '수집시각', '기종', '용량', '통신사', '가입유형', '요금제', '월요금', '출고가', '공시지원금', '추가할인', '할부원금'];
    const csvContent = [
      headers.join(','),
      ...flattenedData.map(row => [
        row.site,
        row.capturedAt,
        row.skuCode,
        row.storage,
        row.carrier,
        row.joinType,
        `"${row.planName}"`, // Handle commas in plan names
        row.monthlyFee,
        row.retailPrice,
        row.publicSubsidy,
        row.discount,
        row.installmentFee
      ].join(','))
    ].join('\n');
      
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'raw_data.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const currentView = useMemo(() => data.views.find(v => v.sku_code === selectedSku), [data, selectedSku]);

  const formattedDate = useMemo(() => {
    try {
      return new Date(data.captured_at).toLocaleString('ko-KR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return data.captured_at;
    }
  }, [data.captured_at]);

  return (
    <div className="bg-gray-50 min-h-screen">
      <header className="fixed top-0 left-0 right-0 h-16 bg-white/80 backdrop-blur-sm border-b border-gray-200 flex items-center justify-between px-4 sm:px-6 z-20">
        <h1 className="text-2xl font-bold text-gray-900">모요 가격 경쟁력 대시보드</h1>
        <div className="text-xs sm:text-sm text-gray-500 text-right">
          마지막 업데이트
          <br className="sm:hidden" />
          <span className="hidden sm:inline">: </span>
          {formattedDate}
        </div>
      </header>

      <div className="pt-16">
        <div className="sticky top-16 bg-white/80 backdrop-blur-sm shadow-sm p-4 border-b border-gray-200 z-10">
          <div className="max-w-screen-xl mx-auto flex flex-wrap items-center justify-between gap-4">
            <div>
              <label htmlFor="sku-select" className="text-sm font-semibold text-gray-700 mb-2 block">기종 선택</label>
              <div className="relative">
                <select
                  id="sku-select"
                  value={selectedSku}
                  onChange={(e) => setSelectedSku(e.target.value)}
                  className="appearance-none w-full sm:w-auto bg-white border-2 border-gray-300 text-gray-700 py-2 px-4 pr-8 rounded-lg leading-tight text-sm font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#516AEC] focus:border-[#516AEC]"
                >
                  {data.filters.sku_codes.map(sku => (
                    <option key={sku.value} value={sku.value}>
                      {sku.label}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-700">
                  <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/></svg>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 pt-2">
              <span className="text-sm text-gray-600 whitespace-nowrap">
                현재: <span className="font-medium text-gray-800">{fileName}</span>
              </span>
              <label className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg border-2 border-gray-300 cursor-pointer hover:bg-gray-200 transition-colors">
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <span className="text-sm font-medium whitespace-nowrap">📁 JSON 업로드</span>
              </label>
              <button
                onClick={handleReset}
                className="px-3 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              >
                초기화
              </button>
            </div>
          </div>
        </div>

        <main className="max-w-screen-xl mx-auto px-4 sm:px-6 py-8">
          <div className="bg-white border-b border-gray-200 mb-6">
            <div className="flex gap-1">
              <button
                onClick={() => setActiveTab("table")}
                className={`px-6 py-3 font-medium text-sm transition-colors ${
                  activeTab === "table"
                    ? "text-[#516AEC] border-b-2 border-[#516AEC]"
                    : "text-gray-600 hover:text-gray-800"
                }`}
              >
                비교 테이블
              </button>
              <button
                onClick={() => setActiveTab("chart")}
                className={`px-6 py-3 font-medium text-sm transition-colors ${
                  activeTab === "chart"
                    ? "text-[#516AEC] border-b-2 border-[#516AEC]"
                    : "text-gray-600 hover:text-gray-800"
                }`}
              >
                차트
              </button>
              <button
                onClick={() => setActiveTab("raw")}
                className={`px-6 py-3 font-medium text-sm transition-colors ${
                  activeTab === "raw"
                    ? "text-[#516AEC] border-b-2 border-[#516AEC]"
                    : "text-gray-600 hover:text-gray-800"
                }`}
              >
                Raw 데이터 {rawData && <span className="ml-1 text-xs bg-[#516AEC]/20 text-[#516AEC] px-2 py-0.5 rounded-full">업로드됨</span>}
              </button>
            </div>
          </div>

          {activeTab === 'table' && (
            <div className="flex flex-col gap-8">
              {data.filters.carriers.map(carrier => (
                <CarrierTable key={carrier.value} carrier={carrier} currentView={currentView} />
              ))}
            </div>
          )}

          {activeTab === 'chart' && (
            <div className="bg-white p-6 rounded-lg shadow-sm mb-6 text-center text-gray-500">
              차트 기능은 현재 준비 중입니다.
            </div>
          )}

          {activeTab === 'raw' && (
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              {!rawData ? (
                <div className="p-12 text-center">
                  <div className="text-gray-400 text-5xl mb-4">📁</div>
                  <h3 className="text-lg font-semibold text-gray-700 mb-2">
                    Raw 데이터가 없습니다
                  </h3>
                  <p className="text-sm text-gray-500 mb-4">
                    JSON 파일을 업로드하면 여기에 원본 데이터가 표시됩니다
                  </p>
                  <label className="inline-block px-6 py-3 bg-[#516AEC] text-white rounded-lg cursor-pointer hover:bg-[#4358c9] transition-colors">
                    <input
                      type="file"
                      accept=".json"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                    <span className="text-sm font-medium">📁 JSON 업로드</span>
                  </label>
                </div>
              ) : (
                <>
                  <div className="p-4 bg-gray-50 border-b border-gray-200">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-800">
                          전체 정책 데이터
                        </h3>
                        <p className="text-sm text-gray-600 mt-1">
                          총 {flattenedData.length}개 정책
                        </p>
                      </div>
                      <button
                        onClick={handleDownloadCsv}
                        className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors"
                      >
                        📥 CSV 다운로드
                      </button>
                    </div>
                  </div>
                  
                  <div className="overflow-x-auto max-h-[70vh]">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-100 sticky top-0 z-10">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 border-b whitespace-nowrap">사이트</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 border-b whitespace-nowrap">수집시각</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 border-b whitespace-nowrap">기종</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 border-b whitespace-nowrap">용량</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 border-b whitespace-nowrap">통신사</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 border-b whitespace-nowrap">가입유형</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 border-b whitespace-nowrap">요금제</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 border-b whitespace-nowrap">월요금</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 border-b whitespace-nowrap">출고가</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 border-b whitespace-nowrap">공시지원금</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 border-b whitespace-nowrap">추가할인</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 border-b whitespace-nowrap">할부원금</th>
                        </tr>
                      </thead>
                      <tbody>
                        {flattenedData.map((row, idx) => (
                          <tr key={idx} className="border-b hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm text-gray-900 font-medium whitespace-nowrap">{row.site}</td>
                            <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{row.capturedAt}</td>
                            <td className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap">{row.skuCode}</td>
                            <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{row.storage}</td>
                            <td className="px-4 py-3 text-sm whitespace-nowrap">
                              <span className={`px-2 py-1 rounded text-xs font-medium ${
                                row.carrier === 'SKT' ? 'bg-red-100 text-red-700' :
                                row.carrier === 'KT' ? 'bg-orange-100 text-orange-700' :
                                'bg-pink-100 text-pink-700'
                              }`}>
                                {row.carrier}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{row.joinType}</td>
                            <td className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap">{row.planName}</td>
                            <td className="px-4 py-3 text-sm text-right text-gray-900 whitespace-nowrap">{row.monthlyFee}원</td>
                            <td className="px-4 py-3 text-sm text-right text-gray-600 whitespace-nowrap">{row.retailPrice}원</td>
                            <td className="px-4 py-3 text-sm text-right text-blue-600 font-medium whitespace-nowrap">{row.publicSubsidy}원</td>
                            <td className="px-4 py-3 text-sm text-right text-green-600 font-medium whitespace-nowrap">{row.discount}원</td>
                            <td className="px-4 py-3 text-sm text-right text-gray-900 font-semibold whitespace-nowrap">{row.installmentFee}원</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
