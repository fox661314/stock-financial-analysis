import re
import streamlit as st
import akshare as ak
import matplotlib.pyplot as plt
import pandas as pd

# ---------- 配置项 ----------
REPORT_PERIODS = {
    "2024 一季报": "20240331",
    "2024 半年报": "20240630",
    "2024 三季报": "20240930",
    "2024 年报":   "20241231",
    "2023 一季报": "20230331",
    "2023 半年报": "20230630",
    "2023 三季报": "20230930",
    "2023 年报":   "20231231",
    "2022 年报":   "20221231",
}

METRIC_OPTIONS = {
    "每股收益": "每股收益",
    "每股净资产": "每股净资产",
    "净资产收益率": "净资产收益率",
    "营业总收入": "营业总收入-营业总收入",
    "净利润": "净利润-净利润",
    "营收同比增长": "营业总收入-同比增长",
    "净利润同比增长": "净利润-同比增长",
    "每股经营现金流": "每股经营现金流量",
    "销售毛利率": "销售毛利率",
    "营收季度环比": "营业总收入-季度环比增长",
    "净利润季度环比": "净利润-季度环比增长",
}

CHART_TYPES = ["柱状图", "折线图", "雷达图", "多指标分组柱状图"]

BASE_COLS = ["股票代码", "股票简称"]

# ---------- 工具函数 ----------
@st.cache_data
def get_stock_df():
    return ak.stock_info_a_code_name()

@st.cache_data
def get_yjbb(date: str):
    return ak.stock_yjbb_em(date=date)

def get_codes_by_names(name_input: str, stock_df: pd.DataFrame) -> list[str]:
    names = re.split(r"[,;，；\s]+", name_input.strip())
    names = [n for n in names if n]
    codes = []
    for keyword in names:
        mask = stock_df["name"].str.contains(keyword, case=False, na=False)
        codes.extend(stock_df.loc[mask, "code"].tolist())
    return list(dict.fromkeys(codes))

def to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out

def plot_chart(result: pd.DataFrame, metrics: list[str], chart_type: str, period_label: str):
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    labels = result["股票简称"].tolist()
    fig, ax = plt.subplots(figsize=(10, 5))

    if chart_type == "柱状图":
        values = result[metrics[0]].astype(float)
        ax.bar(labels, values)
        ax.set_ylabel(metrics[0])
        ax.set_title(f"{metrics[0]} 对比（{period_label}）")

    elif chart_type == "折线图":
        values = result[metrics[0]].astype(float)
        ax.plot(labels, values, marker="o")
        ax.set_ylabel(metrics[0])
        ax.set_title(f"{metrics[0]} 对比（{period_label}）")

    elif chart_type == "雷达图":
        import numpy as np
        if len(metrics) < 3:
            st.warning("雷达图至少需要选择 3 个指标")
            return None

        # 归一化到 0~1，便于多指标同图展示
        norm = result[metrics].astype(float).copy()
        for col in metrics:
            col_min, col_max = norm[col].min(), norm[col].max()
            norm[col] = 0.5 if col_max == col_min else (norm[col] - col_min) / (col_max - col_min)

        angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
        angles += angles[:1]
        ax = plt.subplot(111, polar=True)

        for _, row in norm.iterrows():
            values = row[metrics].tolist()
            values += values[:1]
            ax.plot(angles, values, marker="o", label=row["股票简称"])
            ax.fill(angles, values, alpha=0.1)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(metrics)
        ax.set_title(f"多指标雷达图（{period_label}）")
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    elif chart_type == "多指标分组柱状图":
        x = range(len(labels))
        width = 0.8 / len(metrics)
        for i, metric in enumerate(metrics):
            offset = (i - len(metrics) / 2) * width + width / 2
            ax.bar([p + offset for p in x], result[metric].astype(float), width=width, label=metric)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_title(f"多指标对比（{period_label}）")
        ax.legend()

    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    return fig

# ---------- 界面 ----------
st.title("📊 股票财报对比分析")
st.markdown("按名称选股票，再选择报告期、财务指标和图表类型")

col1, col2 = st.columns(2)
with col1:
    user_input = st.text_input("股票名称关键字", value="比亚迪, 上汽集团")
with col2:
    period_label = st.selectbox("报告期", list(REPORT_PERIODS.keys()), index=3)

metrics_display = st.multiselect(
    "财务指标（可多选）",
    list(METRIC_OPTIONS.keys()),
    default=["每股收益", "净资产收益率"],
)
chart_type = st.selectbox("图表类型", CHART_TYPES)

if st.button("生成分析", type="primary"):
    if not user_input.strip():
        st.warning("请输入股票名称。")
    elif not metrics_display:
        st.warning("请至少选择一个财务指标。")
    else:
        with st.spinner("正在拉取数据..."):
            date = REPORT_PERIODS[period_label]
            df = get_yjbb(date)
            stock_df = get_stock_df()
            codes = get_codes_by_names(user_input, stock_df)

            if not codes:
                st.warning("未匹配到任何股票，请检查输入。")
            else:
                metric_cols = [METRIC_OPTIONS[m] for m in metrics_display]
                show_cols = BASE_COLS + metric_cols

                missing_cols = [c for c in show_cols if c not in df.columns]
                if missing_cols:
                    st.error(f"当前报告期缺少字段：{missing_cols}，请升级 akshare 或换报告期。")
                else:
                    result = df[df["股票代码"].isin(codes)][show_cols].copy()
                    result = to_numeric(result, metric_cols)

                    if result.empty:
                        st.warning("匹配到的股票在该报告期没有数据。")
                    else:
                        st.success(f"匹配到 {len(result)} 支股票")
                        st.subheader("📋 财务数据")
                        st.dataframe(result, use_container_width=True)

                        st.subheader("📈 可视化")
                        fig = plot_chart(result, metric_cols, chart_type, period_label)
                        if fig:
                            st.pyplot(fig)