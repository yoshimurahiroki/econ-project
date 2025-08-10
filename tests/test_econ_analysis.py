"""econ_analysis.py のテスト"""

import pytest
import pandas as pd
import numpy as np
from src.econ_analysis import (
    EconAnalyzer, 
    simulate_wage_data, 
    robust_regression_summary
)


class TestSimulateWageData:
    """simulate_wage_data 関数のテスト"""
    
    def test_basic_functionality(self):
        """基本的な機能のテスト"""
        data = simulate_wage_data(n_obs=100, seed=42)
        
        # データフレームの確認
        assert isinstance(data, pd.DataFrame)
        assert len(data) == 100
        
        # カラムの確認
        expected_columns = ['wage', 'log_wage', 'education', 'experience', 'age']
        assert list(data.columns) == expected_columns
        
        # データの範囲チェック
        assert data['education'].min() >= 6
        assert data['education'].max() <= 20
        assert data['experience'].min() >= 0
        assert data['experience'].max() <= 40
        assert data['wage'].min() > 0  # 賃金は正数
    
    def test_reproducibility(self):
        """再現性のテスト"""
        data1 = simulate_wage_data(n_obs=50, seed=123)
        data2 = simulate_wage_data(n_obs=50, seed=123)
        
        pd.testing.assert_frame_equal(data1, data2)
    
    def test_different_sample_sizes(self):
        """異なるサンプルサイズのテスト"""
        for n in [10, 100, 1000]:
            data = simulate_wage_data(n_obs=n, seed=42)
            assert len(data) == n


class TestEconAnalyzer:
    """EconAnalyzer クラスのテスト"""
    
    @pytest.fixture
    def sample_data(self):
        """テスト用サンプルデータ"""
        return simulate_wage_data(n_obs=100, seed=42)
    
    @pytest.fixture 
    def analyzer(self, sample_data):
        """テスト用アナライザー"""
        return EconAnalyzer(sample_data)
    
    def test_initialization(self, sample_data):
        """初期化のテスト"""
        analyzer = EconAnalyzer(sample_data)
        assert isinstance(analyzer.data, pd.DataFrame)
        assert len(analyzer.models) == 0
    
    def test_descriptive_stats(self, analyzer):
        """記述統計のテスト"""
        stats = analyzer.descriptive_stats()
        
        assert isinstance(stats, pd.DataFrame)
        assert 'mean' in stats.columns
        assert 'std' in stats.columns
        assert 'skewness' in stats.columns
        assert 'kurtosis' in stats.columns
        assert 'missing' in stats.columns
    
    def test_mincer_regression_basic(self, analyzer):
        """基本的なMincer回帰のテスト"""
        model = analyzer.mincer_regression(
            dependent_var='log_wage',
            education_var='education', 
            experience_var='experience',
            add_experience_squared=False
        )
        
        # 回帰結果の基本的な確認
        assert model.nobs == 100
        assert len(model.params) == 3  # 定数項 + 2変数
        assert model.rsquared > 0  # R²は正数
        
        # モデルが保存されていることを確認
        assert len(analyzer.models) == 1
    
    def test_mincer_regression_with_squared_term(self, analyzer):
        """経験の2乗項ありのMincer回帰のテスト"""
        model = analyzer.mincer_regression(
            dependent_var='log_wage',
            education_var='education',
            experience_var='experience',
            add_experience_squared=True
        )
        
        # 経験の2乗項が追加されていることを確認
        assert len(model.params) == 4  # 定数項 + 3変数
        assert 'experience_squared' in analyzer.data.columns
    
    def test_calculate_returns_to_education(self, analyzer):
        """教育収益率計算のテスト"""
        model = analyzer.mincer_regression(
            dependent_var='log_wage',
            education_var='education',
            experience_var='experience'
        )
        
        returns = analyzer.calculate_returns_to_education(model, 'education')
        
        # 戻り値の構造確認
        expected_keys = [
            'coefficient', 'return_percent', 'std_error', 
            't_statistic', 'p_value', 'significant_5pct'
        ]
        for key in expected_keys:
            assert key in returns
        
        # 値の妥当性確認
        assert isinstance(returns['coefficient'], (int, float))
        assert isinstance(returns['return_percent'], (int, float))
        assert isinstance(returns['significant_5pct'], bool)
    
    def test_empty_models_dict_initially(self, analyzer):
        """初期状態でmodels辞書が空であることのテスト"""
        assert len(analyzer.models) == 0
    
    def test_models_stored_after_regression(self, analyzer):
        """回帰実行後にモデルが保存されることのテスト"""
        analyzer.mincer_regression(
            dependent_var='log_wage',
            education_var='education',
            experience_var='experience'
        )
        
        assert len(analyzer.models) == 1
        assert 'mincer_log_wage' in analyzer.models


class TestRobustRegressionSummary:
    """robust_regression_summary 関数のテスト"""
    
    def test_basic_functionality(self):
        """基本的な機能のテスト"""
        # テストデータとモデルの準備
        data = simulate_wage_data(n_obs=100, seed=42)
        analyzer = EconAnalyzer(data)
        
        model1 = analyzer.mincer_regression('log_wage', 'education', 'experience', False)
        model2 = analyzer.mincer_regression('log_wage', 'education', 'experience', True)
        
        models = [model1, model2]
        names = ['Model1', 'Model2']
        
        summary = robust_regression_summary(models, names)
        
        # 結果の確認
        assert isinstance(summary, pd.DataFrame)
        assert len(summary) == 2
        assert list(summary.index) == names
        
        # 統計量の確認
        expected_columns = [
            'R-squared', 'Adj R-squared', 'F-statistic', 
            'F p-value', 'AIC', 'BIC', 'N observations'
        ]
        for col in expected_columns:
            assert col in summary.columns
    
    def test_mismatched_lengths(self):
        """リストの長さが不一致の場合のエラーテスト"""
        data = simulate_wage_data(n_obs=50, seed=42)
        analyzer = EconAnalyzer(data)
        model = analyzer.mincer_regression('log_wage', 'education', 'experience')
        
        with pytest.raises(ValueError):
            robust_regression_summary([model], ['Model1', 'Model2'])


class TestIntegration:
    """統合テスト"""
    
    def test_full_analysis_workflow(self):
        """完全な分析ワークフローのテスト"""
        # データ生成
        data = simulate_wage_data(n_obs=200, seed=123)
        
        # 分析実行
        analyzer = EconAnalyzer(data)
        
        # 記述統計
        desc_stats = analyzer.descriptive_stats()
        assert not desc_stats.empty
        
        # 回帰分析
        model1 = analyzer.mincer_regression('log_wage', 'education', 'experience', False)
        model2 = analyzer.mincer_regression('log_wage', 'education', 'experience', True)
        
        # 教育収益率
        returns = analyzer.calculate_returns_to_education(model1, 'education')
        assert returns['return_percent'] > 0  # 正の収益率が期待される
        
        # モデル比較
        summary = robust_regression_summary([model1, model2], ['Basic', 'With_Squared'])
        assert summary.loc['With_Squared', 'R-squared'] >= summary.loc['Basic', 'R-squared']
