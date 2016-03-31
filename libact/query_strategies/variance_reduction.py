"""Variance Reduction"""

import copy
from multiprocessing import Pool

import numpy as np

from libact.base.interfaces import QueryStrategy
from libact.base.dataset import Dataset
import libact.models
from libact.query_strategies._variance_reduction import estVar


class VarianceReduction(QueryStrategy):
    """Variance Reduction

    This class implements Variance Reduction active learning algorithm [1]_.

    Parameters
    ----------
    model: {libact.model.LogisticRegression instance, 'LogisticRegression'}
        The model used for variance reduction to evaluate the variance.
        Only Logistic regression are supported now.

    sigma: float, >0, optional (default=100.0)
        1/sigma is added to the diagonal of the Fisher information matrix as a
        regularization term.

    optimality : {'trace', 'determinant', 'eigenvalue'}, optional (default='trace')
        The type of optimal design.  The options are the trace, determinant, or
        maximum eigenvalue of the inverse Fisher information matrix.
        Only 'trace' are supported now.


    Attributes
    ----------


    References
    ----------
    .. [1] Schein, Andrew I., and Lyle H. Ungar. "Active learning for logistic
           regression: an evaluation." Machine Learning 68.3 (2007): 235-265.

    .. [2] Settles, Burr. "Active learning literature survey." University of
           Wisconsin, Madison 52.55-66 (2010): 11.
    """

    def __init__(self,  *args, **kwargs):
        super(VarianceReduction, self).__init__(*args, **kwargs)
        model = kwargs.pop('model', None)
        if type(model) is str:
            self.model = getattr(libact.models, model)()
        else:
            self.model = model
        self.optimality = kwargs.pop('optimality', 'trace')
        self.sigma = kwargs.pop('sigma', 1.0)

    def Phi(self, PI, X, epi, ex, label_count, feature_count):
        ret = estVar(self.sigma, PI, X, epi, ex)
        return ret

    def E(self, args):
        X, y, qx, clf, label_count = args
        sigmoid = lambda x: 1 / (1 + np.exp(-x))
        query_point = sigmoid(clf.predict_real([qx]))
        feature_count = len(X[0])
        ret = 0.0
        for i in range(label_count):
            clf = copy.copy(self.model)
            clf.train(Dataset(np.vstack((X, [qx])), np.append(y, i)))
            PI = sigmoid(clf.predict_real(np.vstack((X, [qx]))))
            ret += query_point[-1][i] * self.Phi(PI[:-1], X, PI[-1], qx,
                    label_count, feature_count)
        return ret

    def make_query(self, n_jobs=1):
        """
        Calculate which point to query.

        Parameters
        ----------
        n_jobs : int, optional (default=1)
            The number of jobs to run in parallel.

        Returns
        -------
        ask_id : int
            The entry id of the sample wants to query.
        """
        labeled_entries = self.dataset.get_labeled_entries()
        Xlabeled, y = zip(*labeled_entries)
        Xlabeled = np.array(Xlabeled)
        y = list(y)

        unlabeled_entries = self.dataset.get_unlabeled_entries()
        unlabeled_entry_ids, X_pool = zip(*unlabeled_entries)

        label_count = self.dataset.get_num_of_labels()

        clf = copy.copy(self.model)
        clf.train(Dataset(Xlabeled, y))

        p = Pool(n_jobs)

        errors = p.map(self.E, [(Xlabeled, y, x, clf, label_count) for x in
                                X_pool])
        p.terminate()
        return unlabeled_entry_ids[errors.index(min(errors))]
