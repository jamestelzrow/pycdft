from pycdft.common.sample import *


class WfcManager:
    r"""Helper class to manage a collection of quantities like :math:`\psi(r)' or :math:`\psi(G)`.

    The collection can be indexed by either an internal index or a (spin, kpoint, band) index.
    """

    def __init__(self, wfc, transform=lambda f: f):
        self.wfc = wfc
        self.qty = dict()
        self.transform = transform

    def indices(self):
        return self.qty.keys()

    def clear(self):
        self.qty.clear()

    def _get_idx(self, key):
        try:
            idx = int(key)
        except TypeError:
            try:
                ispin = int(key[0])
                ikpt = int(key[1])
                ibnd = int(key[2])
                assert 0 <= ispin <= self.wfc.nspin
                assert 0 <= ikpt <= self.wfc.nkpt
                assert 0 <= ibnd <= self.wfc.nbnd[ispin, ikpt]
            except ValueError:
                raise ValueError("Index must be either internal index or (spin, kpoint, band) index")
            except (AssertionError, IndexError):
                raise IndexError("(spin, kpoint, band) index out of range ({}, {}, {})".format(
                    self.wfc.nspin, self.wfc.nkpt, self.wfc.nbnd
                ))
            idx = self.wfc.skb2idx(ispin, ikpt, ibnd)
        return idx

    def __getitem__(self, key):
        return self.qty[self._get_idx(key)]

    def __setitem__(self, key, value):
        idx = self._get_idx(key)
        self.qty[idx] = self.transform(value)


class Wavefunction:
    """Container class for Kohn-Sham wavefunction.

    A wavefunction is defined as a collection of KS orbitals, each uniquely labeled by
    three integers: spin (0 or 1), k point index and band index. To facilitate distributed
    storage and access of a wavefunction on multiple processors, each KS orbital is also
    uniquelly labeled by an internal index. Internal index (idx) is generated by following
    pattern::

        for ispin in range(nspin):
            for ikpt in range(nkpt):
                for ibnd in range(nbnd[ispin, ikpt]):
                    idx ++

    Currently, k points are not fully supported.

    Note:
         ``psi_r`` and ``psi_g`` can be accessed like dicts. They can be indexed with either
         an integer (internal index) or a 3-tuple of integers (spin, kpoint, band index).
         After been indexed, the corresponding quantity (numpy array) of a
         specific KS orbital is returned.

    Attributes:
         psi_r: R space KS orbitals defined on a R space grid described by self.wgrid.
         psi_g: G space KS orbitals defined on a G space grid described by self.wgrid.
      
         sample (Sample): sample upon which the wavefunction is defined.
         wgrid (FFTGrid): wavefunction grid.
         dgrid (FFTGrid): charge density grid.
      
         nspin (int): # of spin channel. 1: spin unpolarized; 2: spin polarized.
         nkpt (int): # of k points.
         nbnd (int): # of bands.
         norb (int): total # of orbitals on all spins, kpoints.
         occ (array): occupation numbers. shape: (nspin, nkpt, nbnd).
     
         idx_skb_map (dict): private, internal index -> (spin, kpoint, band) index map; access with skb2idx
         skb_idx_map (dict): private, (spin, kpoint, band) index -> internal index map; access with idx2skb
    """

    def __init__(self, sample: Sample, wgrid, dgrid, nspin, nkpt, nbnd, occ, gamma=True):

        # define general info
        self.sample = sample
        self.wgrid = wgrid
        self.dgrid = dgrid

        self.nspin = nspin
        self.nkpt = nkpt
        assert self.nkpt == 1, "K points are not supported yet"
        try:
            nbnd_ = int(nbnd)
            # all spin and kpoints share the same nbnd
            self.nbnd = np.ones((self.nspin, self.nkpt), dtype=int) * nbnd_
        except TypeError:
            # every spin and kpoint have its own nbnd
            self.nbnd = np.array(nbnd, dtype=np.int_)
            assert self.nbnd.shape == (self.nspin, self.nkpt)
        if occ.ndim == 1:
            # all spin and kpoints share the same occupation
            self.occ = np.tile(occ, (self.nspin, self.nkpt)).reshape(self.nspin, self.nkpt, -1)
        else:
            # every spin and kpoint have its own occupation
            self.occ = np.zeros((self.nspin, self.nkpt, np.max(self.nbnd)), dtype=int)
            for ispin in range(self.nspin):
                for ikpt in range(self.nkpt):
                    nbnd = self.nbnd[ispin, ikpt]
                    self.occ[ispin, ikpt, 0:nbnd] = occ[ispin, ikpt][0:nbnd]

        self.gamma = gamma

        # define maps between internal index <-> (spin, kpoint, band) index
        self.idx_skb_map = dict()
        idx = 0
        for ispin, ikpt in np.ndindex(self.nspin, self.nkpt):
            for ibnd in range(self.nbnd[ispin, ikpt]):
                self.idx_skb_map[idx] = (ispin, ikpt, ibnd)
                idx += 1
        self.norb = len(self.idx_skb_map)
        self.skb_idx_map = {
            self.idx_skb_map[idx]: idx
            for idx in range(self.norb)
        }

        # define containers to store collections of psi(r) or psi(G)
        self.psi_g = WfcManager(self)
        self.psi_r = WfcManager(self, transform=self.normalize)

    def skb2idx(self, ispin, ikpt, ibnd):
        """Get internal index from (spin, kpoint, band) index."""
        try:
            return self.skb_idx_map[ispin, ikpt, ibnd]
        except KeyError:
            return None

    def idx2skb(self, idx):
        """Get (spin, kpoint, band) index from internal index."""
        return self.idx_skb_map[idx]

    def normalize(self, psir):
        """Normalize psi(r)."""
        assert psir.shape == (self.wgrid.n1, self.wgrid.n2, self.wgrid.n3)
        norm = np.sqrt(np.sum(np.abs(psir) ** 2) * self.sample.omega / self.wgrid.N)
        return psir / norm
