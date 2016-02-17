__author__ = "Mikael Mortensen <mikaem@math.uio.no>"
__date__ = "2016-02-16"
__copyright__ = "Copyright (C) 2016 " + __author__
__license__  = "GNU Lesser GPL version 3 or any later version"

from serialFFT import *
import numpy as np

#__all__ = ['FastFourierTransform']

def transform_Uc_xz(Uc_hat_x, Uc_hat_z, P1):
    #n0 = Uc_hat_z.shape[0]
    #n1 = Uc_hat_x.shape[2]
    #for i in range(P1):
        #Uc_hat_x[i*n0:(i+1)*n0] = Uc_hat_z[:, :, i*n1:(i+1)*n1]
        
    sz = Uc_hat_z.shape
    sx = Uc_hat_x.shape
    Uc_hat_x[:] = np.rollaxis(Uc_hat_z[:,:,:-1].reshape((sz[0], sz[1], P1, sx[2])), 2).reshape(sx)
    return Uc_hat_x
            
def transform_Uc_zx(Uc_hat_z, Uc_hat_xr, P1):
    #n0 = Uc_hat_z.shape[0]
    #n1 = Uc_hat_xr.shape[2]
    #for i in range(P1):
        #Uc_hat_z[:, :, i*n1:(i+1)*n1] = Uc_hat_xr[i*n0:(i+1)*n0]
        
    sz = Uc_hat_z.shape
    sx = Uc_hat_xr.shape
    Uc_hat_z[:, :, :-1] = np.rollaxis(Uc_hat_xr.reshape((P1, sz[0], sz[1], sx[2])), 0, 3).reshape((sz[0], sz[1], sz[2]-1))        
    return Uc_hat_z

def transform_Uc_xy(Uc_hat_x, Uc_hat_y, P):
    #n0 = Uc_hat_y.shape[0]
    #n1 = Uc_hat_x.shape[1]
    #for i in range(P): 
        #Uc_hat_x[i*n0:(i+1)*n0] = Uc_hat_y[:, i*n1:(i+1)*n1]
        
    sy = Uc_hat_y.shape
    sx = Uc_hat_x.shape
    Uc_hat_x[:] = np.rollaxis(Uc_hat_y.reshape((sy[0], P, sx[1], sx[2])), 1).reshape(sx)        
    return Uc_hat_x

def transform_Uc_yx(Uc_hat_y, Uc_hat_x, P):
    #n0 = Uc_hat_y.shape[0]
    #n1 = Uc_hat_x.shape[1]
    #for i in range(P): 
        #Uc_hat_y[:, i*n1:(i+1)*n1] = Uc_hat_x[i*n0:(i+1)*n0]
        
    sy = Uc_hat_y.shape
    sx = Uc_hat_x.shape
    Uc_hat_y[:] = np.rollaxis(Uc_hat_x.reshape((P, sy[0], sx[1], sx[2])), 1).reshape(sy)          
    return Uc_hat_y

def transform_Uc_yz(Uc_hat_y, Uc_hat_z, P):
    #n0 = Uc_hat_z.shape[1]
    #n1 = Uc_hat_y.shape[2]
    #for i in range(P):
        #Uc_hat_y[:, i*n0:(i+1)*n0] = Uc_hat_z[:, :, i*n1:(i+1)*n1]
        
    sz = Uc_hat_z.shape
    sy = Uc_hat_y.shape
    Uc_hat_y[:] = np.rollaxis(Uc_hat_z[:,:,:-1].reshape((sz[0], sz[1], P, sy[2])), 1, 3).reshape(sy)
    return Uc_hat_y

def transform_Uc_zy(Uc_hat_z, Uc_hat_y, P):
    #n0 = Uc_hat_z.shape[1]
    #n1 = Uc_hat_y.shape[2]
    #for i in range(P):
        #Uc_hat_z[:, :, i*n1:(i+1)*n1] = Uc_hat_y[:, i*n0:(i+1)*n0] 

    sz = Uc_hat_z.shape
    sy = Uc_hat_y.shape
    Uc_hat_z[:, :, :-1] = np.rollaxis(Uc_hat_y.reshape((sy[0], P, sz[1], sy[2])), 1, 3).reshape((sz[0], sz[1], sz[2]-1)) 
    return Uc_hat_z

class FastFourierTransformY(object):
    """Class for performing FFT in 3D using MPI
    
    Pencil decomposition
    
    N - NumPy array([Nx, Ny, Nz]) setting the dimensions of the real mesh
    L - NumPy array([Lx, Ly, Lz]) setting the actual size of the real mesh
    MPI - The MPI object (from mpi4py import MPI)
    precision - "single" or "double"
    
    This version has the final complex data aligned in the y-direction, in agreement
    with the paper in CPC (http://arxiv.org/pdf/1602.03638v1.pdf)
    
    """

    def __init__(self, N, L, MPI, precision, P1=None):
        self.N = N
        self.L = L
        assert len(L) == 3
        assert len(N) == 3
        self.Nf = Nf = N[2]/2+1 # Number of independent complex wavenumbers in z-direction 
        self.MPI = MPI
        self.comm = comm = MPI.COMM_WORLD
        self.float, self.complex, self.mpitype = float, complex, mpitype = self.types(precision)
        self.num_processes = comm.Get_size()
        assert self.num_processes > 1
        
        self.rank = comm.Get_rank()
        if P1 is None:
            P1 = self.num_processes / 2
        self.P1 = P1
        self.P2 = P2 = self.num_processes / P1
        self.N1 = N1 = N / P1
        self.N2 = N2 = N / P2
        self.comm0 = comm.Split(self.rank/P1)
        self.comm1 = comm.Split(self.rank%P1)
        
        if not (self.num_processes % 2 == 0 or self.num_processes == 1):
            raise IOError("Number of cpus must be even")

        if ((P1 % 2 != 0) or (P2 % 2 != 0)):
            raise IOError("Number of cpus in each direction must be even power of 2")
        
        self.init_work_arrays()

    def init_work_arrays(self):
        # Initialize MPI work arrays globally
        self.Uc_hat_z  = empty((self.N1[0], self.N2[1], self.Nf), dtype=self.complex)
        self.Uc_hat_x  = empty((self.N[0], self.N2[1], self.N1[2]/2), dtype=self.complex)
        self.Uc_hat_xr = empty((self.N[0], self.N2[1], self.N1[2]/2), dtype=self.complex)
        self.Uc_hat_y  = zeros((self.N2[0], self.N[1], self.N1[2]/2), dtype=self.complex)

    def types(self, precision):
        return {"single": (np.float32, np.complex64, self.MPI.F_FLOAT_COMPLEX),
                "double": (np.float64, np.complex128, self.MPI.F_DOUBLE_COMPLEX)}[precision]

    def real_shape(self):
        """The local shape of the real data"""
        return (self.N1[0], self.N2[1], self.N[2])

    def complex_shape(self):
        """The local shape of the complex data"""
        return (self.N2[0], self.N[1], self.N1[2]/2)
    
    def complex_shape_T(self):
        """The local transposed shape of the complex data"""
        return (self.Np[0], self.N[1], self.Nf)
        
    def complex_shape_I(self):
        """A local intermediate shape of the complex data"""
        return (self.Np[0], self.num_processes, self.Np[1], self.Nf)

    #def complex_shape_padded_T(self):
        #"""The local shape of the transposed complex data padded in x and z directions"""
        #return (3*self.Np[0]/2, 3*self.N[1]/2, 3*self.N[2]/4+1)

    #def real_shape_padded(self):
        #"""The local shape of the real data"""
        #return (3*self.Np[0]/2, 3*self.N[1]/2, 3*self.N[2]/2)
    
    #def complex_shape_padded(self):
        #return (3*self.N[0]/2, 3*self.Np[1]/2, 3*self.N[2]/4+1)
        
    def get_P(self):
        return self.P1, self.P2
    
    def get_N(self):
        return self.N
    
    def get_local_mesh(self):
        xzrank = self.comm0.Get_rank() # Local rank in xz-plane
        xyrank = self.comm1.Get_rank() # Local rank in xy-plane
        
        # Create the physical mesh
        x1 = slice(xzrank * self.N1[0], (xzrank+1) * self.N1[0], 1)
        x2 = slice(xyrank * self.N2[1], (xyrank+1) * self.N2[1], 1)
        X = np.mgrid[x1, x2, :self.N[2]].astype(self.float)
        X[0] *= self.L[0]/self.N[0]
        X[1] *= self.L[1]/self.N[1]
        X[2] *= self.L[2]/self.N[2] 
        return X

    def get_local_wavenumbermesh(self):
        xzrank = self.comm0.Get_rank() # Local rank in xz-plane
        xyrank = self.comm1.Get_rank() # Local rank in xy-plane

        # Set wavenumbers in grid
        kx = fftfreq(self.N[0], 1./self.N[0]).astype(int)
        ky = fftfreq(self.N[1], 1./self.N[1]).astype(int)
        kz = fftfreq(self.N[2], 1./self.N[2]).astype(int)
        k2 = slice(xyrank*self.N2[0], (xyrank+1)*self.N2[0], 1)
        k1 = slice(xzrank*self.N1[2]/2, (xzrank+1)*self.N1[2]/2, 1)
        K  = np.array(np.meshgrid(kx[k2], ky, kz[k1], indexing='ij'), dtype=self.float)
        return K

    def get_scaled_local_wavenumbermesh(self):
        K = self.get_local_wavenumbermesh()
        # Scale with physical mesh size. This takes care of mapping the physical domain to a computational cube of size (2pi)**3
        Lp = 2*np.pi/self.L
        for i in range(3):
            K[i] *= Lp[i] 
        return K
    
    def get_dealias_filter(self):
        """Filter for dealiasing nonlinear convection"""
        K = self.get_local_wavenumbermesh()
        kmax = 2./3.*(self.N/2+1)
        dealias = np.array((abs(K[0]) < kmax[0])*(abs(K[1]) < kmax[1])*
                           (abs(K[2]) < kmax[2]), dtype=np.uint8)
        return dealias
        
    def ifftn(self, fu, u):
        """ifft in three directions using mpi.
        Need to do ifft in reversed order of fft
        """
        # Do first owned direction
        self.Uc_hat_y[:] = ifft(fu, axis=1)

        # Transform to x all but k=N/2 (the neglected Nyquist mode)
        self.Uc_hat_x[:] = 0
        self.Uc_hat_x[:] = transform_Uc_xy(self.Uc_hat_x, self.Uc_hat_y, self.P2)
            
        # Communicate in xz-plane and do fft in x-direction
        self.comm1.Alltoall([self.Uc_hat_x, self.mpitype], [self.Uc_hat_xr, self.mpitype])
        self.Uc_hat_x[:] = ifft(self.Uc_hat_xr, axis=0)
            
        # Communicate and transform in xy-plane
        self.comm0.Alltoall([self.Uc_hat_x, self.mpitype], [self.Uc_hat_xr, self.mpitype])
        self.Uc_hat_z[:] = transform_Uc_zx(self.Uc_hat_z, self.Uc_hat_xr, self.P1)
                
        # Do fft for y-direction
        self.Uc_hat_z[:, :, -1] = 0
        u[:] = irfft(self.Uc_hat_z, axis=2)
        return u

    def fftn(self, u, fu):
        """fft in three directions using mpi
        """
        # Do fft in z direction on owned data
        self.Uc_hat_z[:] = rfft(u, axis=2)
        
        # Transform to x direction neglecting k=N/2 (Nyquist)
        self.Uc_hat_x[:] = transform_Uc_xz(self.Uc_hat_x, self.Uc_hat_z, self.P1)
        
        # Communicate and do fft in x-direction
        self.comm0.Alltoall([self.Uc_hat_x, self.mpitype], [self.Uc_hat_xr, self.mpitype])
        self.Uc_hat_x[:] = fft(self.Uc_hat_xr, axis=0)        
        
        # Communicate and transform to final z-direction
        self.comm1.Alltoall([self.Uc_hat_x, self.mpitype], [self.Uc_hat_xr, self.mpitype])  
        self.Uc_hat_y[:] = transform_Uc_yx(self.Uc_hat_y, self.Uc_hat_xr, self.P2)
                                    
        # Do fft for last direction 
        fu[:] = fft(self.Uc_hat_y, axis=1)
        return fu


class FastFourierTransformX(FastFourierTransformY):
    """Class for performing FFT in 3D using MPI
    
    Pencil decomposition
    
    N - NumPy array([Nx, Ny, Nz]) setting the dimensions of the real mesh
    L - NumPy array([Lx, Ly, Lz]) setting the actual size of the real mesh
    MPI - The MPI object (from mpi4py import MPI)
    precision - "single" or "double"
    
    This version has the final complex data aligned in the x-direction
    
    """
    
    def __init__(self, N, L, MPI, precision, P1=None):
        FastFourierTransformY.__init__(self, N, L, MPI, precision, P1=P1)

    def init_work_arrays(self):
        # Initialize MPI work arrays globally
        self.Uc_hat_z  = empty((self.N1[0], self.N2[1], self.Nf), dtype=self.complex)
        self.Uc_hat_y  = zeros((self.N1[0], self.N[1], self.N2[2]/2), dtype=self.complex)
        self.Uc_hat_yr = zeros((self.N1[0], self.N[1], self.N2[2]/2), dtype=self.complex)
        self.Uc_hat_x  = empty((self.N[0], self.N1[1], self.N2[2]/2), dtype=self.complex)
        self.Uc_hat_xr  = empty((self.N[0], self.N1[1], self.N2[2]/2), dtype=self.complex)        
        self.Uc_hat_y_T  = zeros((self.N[1], self.N1[0], self.N2[2]/2), dtype=self.complex)
        self.Uc_hat_yr_T  = zeros((self.N[1], self.N1[0], self.N2[2]/2), dtype=self.complex)

    def real_shape(self):
        """The local shape of the real data"""
        return (self.N1[0], self.N2[1], self.N[2])

    def complex_shape(self):
        """The local shape of the complex data"""
        return (self.N[0], self.N1[1], self.N2[2]/2)
    
    def complex_shape_T(self):
        """The local transposed shape of the complex data"""
        return (self.Np[0], self.N[1], self.Nf)
        
    def complex_shape_I(self):
        """A local intermediate shape of the complex data"""
        return (self.Np[0], self.num_processes, self.Np[1], self.Nf)

    #def complex_shape_padded_T(self):
        #"""The local shape of the transposed complex data padded in x and z directions"""
        #return (3*self.Np[0]/2, 3*self.N[1]/2, 3*self.N[2]/4+1)

    #def real_shape_padded(self):
        #"""The local shape of the real data"""
        #return (3*self.Np[0]/2, 3*self.N[1]/2, 3*self.N[2]/2)
    
    #def complex_shape_padded(self):
        #return (3*self.N[0]/2, 3*self.Np[1]/2, 3*self.N[2]/4+1)
            
    def get_local_mesh(self):
        xyrank = self.comm0.Get_rank() # Local rank in xz-plane
        yzrank = self.comm1.Get_rank() # Local rank in xy-plane
        
        # Create the physical mesh
        x1 = slice(xyrank * self.N1[0], (xyrank+1) * self.N1[0], 1)
        x2 = slice(yzrank * self.N2[1], (yzrank+1) * self.N2[1], 1)
        X = np.mgrid[x1, x2, :self.N[2]].astype(self.float)
        X[0] *= self.L[0]/self.N[0]
        X[1] *= self.L[1]/self.N[1]
        X[2] *= self.L[2]/self.N[2] 
        return X

    def get_local_wavenumbermesh(self):
        xyrank = self.comm0.Get_rank() # Local rank in xz-plane
        yzrank = self.comm1.Get_rank() # Local rank in yz-plane

        # Set wavenumbers in grid
        kx = fftfreq(self.N[0], 1./self.N[0]).astype(int)
        ky = fftfreq(self.N[1], 1./self.N[1]).astype(int)
        kz = fftfreq(self.N[2], 1./self.N[2]).astype(int)
        k2 = slice(xyrank*self.N1[1], (xyrank+1)*self.N1[1], 1)
        k1 = slice(yzrank*self.N2[2]/2, (yzrank+1)*self.N2[2]/2, 1)
        K  = np.array(np.meshgrid(kx, ky[k2], kz[k1], indexing='ij'), dtype=self.float)
        return K
        
    def ifftn(self, fu, u):
        """ifft in three directions using mpi.
        Need to do ifft in reversed order of fft
        """
        # Do first owned direction
        self.Uc_hat_x[:] = ifft(fu, axis=0)

        # Communicate in xz-plane and do fft in y-direction
        self.comm0.Alltoall([self.Uc_hat_x, self.mpitype], [self.Uc_hat_xr, self.mpitype])
        
        # Transform to y all but k=N/2 (the neglected Nyquist mode)
        self.Uc_hat_y[:] = 0
        self.Uc_hat_y[:] = transform_Uc_yx(self.Uc_hat_y, self.Uc_hat_xr, self.P1)            
        self.Uc_hat_y[:] = ifft(self.Uc_hat_y, axis=1)
            
        # Communicate and transform in yz-plane
        self.Uc_hat_y_T[:] = self.Uc_hat_y.transpose((1, 0, 2))
        self.comm1.Alltoall([self.Uc_hat_y_T, self.mpitype], 
                             [self.Uc_hat_yr_T, self.mpitype])
        self.Uc_hat_y[:] = self.Uc_hat_yr_T.transpose((1, 0, 2))
        self.Uc_hat_z[:] = transform_Uc_zy(self.Uc_hat_z, self.Uc_hat_y, self.P2)
                
        # Do ifft for y-direction
        self.Uc_hat_z[:, :, -1] = 0
        u[:] = irfft(self.Uc_hat_z, axis=2)
        return u

    def fftn(self, u, fu):
        """fft in three directions using mpi
        """
        # Do fft in z direction on owned data
        self.Uc_hat_z[:] = rfft(u, axis=2)
        
        # Transform to y direction neglecting k=N/2 (Nyquist)
        self.Uc_hat_y[:] = transform_Uc_yz(self.Uc_hat_y, self.Uc_hat_z, self.P2)
        
        # Communicate and do fft in x-direction
        self.Uc_hat_y_T[:] = self.Uc_hat_y.transpose((1, 0, 2))
        self.comm1.Alltoall([self.Uc_hat_y_T, self.mpitype], 
                             [self.Uc_hat_yr_T, self.mpitype])
        self.Uc_hat_y[:] = self.Uc_hat_yr_T.transpose((1, 0, 2))
        self.Uc_hat_yr[:] = fft(self.Uc_hat_y, axis=1)
        
        # Communicate and transform to final z-direction
        self.Uc_hat_x[:] = transform_Uc_xy(self.Uc_hat_x, self.Uc_hat_yr, self.P1)
        self.comm0.Alltoall([self.Uc_hat_x, self.mpitype], [self.Uc_hat_xr, self.mpitype])  
                                    
        # Do fft for last direction 
        fu[:] = fft(self.Uc_hat_xr, axis=0)
        return fu

FastFourierTransform = {
    "X": FastFourierTransformX,
    "Y": FastFourierTransformY
    }
        