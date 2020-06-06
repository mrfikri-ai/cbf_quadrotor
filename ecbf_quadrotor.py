"""ecbf_quadrotor.py
Exponential Control Barrier Function with Quadrotor Dynamics

`python ecbf_quadrotor.py` to see two robots navigating towards each other, with safe control
"""
from dynamics import QuadDynamics
from controller import *
import numpy as np
import matplotlib.pyplot as plt
from cvxopt import matrix
from cvxopt import solvers
import time

a = 1
b = 2
safety_dist = 2

class ECBF_control():
    def __init__(self, state, goal=np.array([[0], [10]]), Kp=3, Kd=4):
        self.state = state
        self.shape_dict = {} 
        # Kp = 3
        # Kd = 4
        self.K = np.array([Kp, Kd])
        self.goal=goal
        self.use_safe = True

    def compute_plot_z(self, obs):
        plot_x = np.arange(-7.5, 7.5, 0.1)
        plot_y = np.arange(-7.5, 7.5, 0.1)
        xx, yy = np.meshgrid(plot_x, plot_y, sparse=True)
        z = h_func(xx - obs[0], yy - obs[1], a, b, safety_dist) > 0
        p = {"x":plot_x, "y":plot_y, "z":z}
        return p
        
    def plot_h(self, plot_x, plot_y, z):
        h = plt.contourf(plot_x, plot_y, z,
                         [-1, 0, 1], colors=["grey", "white"])
        plt.xlabel("X")
        plt.ylabel("Y")
        plt.legend()
        plt.pause(0.00000001)



    def compute_h(self, obs=np.array([[0], [0]]).T):
        rel_r = np.atleast_2d(self.state["x"][:2]).T - obs
        # TODO: a, safety_dist, obs, b
        hr = h_func(rel_r[0], rel_r[1], a, b, safety_dist)
        return hr

    def compute_hd(self, obs):
        rel_r = np.atleast_2d(self.state["x"][:2]).T - obs
        rd = np.atleast_2d(self.state["xdot"][:2]).T
        term1 = (4 * np.power(rel_r[0],3) * rd[0])/(np.power(a,4))
        term2 = (4 * np.power(rel_r[1],3) * rd[1])/(np.power(b,4))
        return term1+term2

    def compute_A(self, obs):
        rel_r = np.atleast_2d(self.state["x"][:2]).T - obs
        A0 = (4 * np.power(rel_r[0], 3))/(np.power(a, 4))
        A1 = (4 * np.power(rel_r[1], 3))/(np.power(b, 4))

        return np.array([np.hstack((A0, A1))])

    def compute_h_hd(self, obs):
        h = self.compute_h(obs)
        hd = self.compute_hd(obs)

        return np.vstack((h, hd)).astype(np.double)

    def compute_b(self, obs):
        """extra + K * [h hd]"""
        rel_r = np.atleast_2d(self.state["x"][:2]).T - obs
        rd = np.array(np.array(self.state["xdot"])[:2])
        extra = -(
            (12 * np.square(rel_r[0]) * np.square(rd[0]))/np.power(a,4) +
            (12 * np.square(rel_r[1]) * np.square(rd[1]))/np.power(b, 4)
        )

        b_ineq = extra - self.K @ self.compute_h_hd(obs)
        return b_ineq

    def compute_safe_control(self,obs):
        if self.use_safe:
            A = self.compute_A(obs)
            assert(A.shape == (1,2))

            b_ineq = self.compute_b(obs)

            #Make CVXOPT quadratic programming problem
            P = matrix(np.eye(2), tc='d')
            q = -1 * matrix(self.compute_nom_control(), tc='d')
            G = -1 * matrix(A.astype(np.double), tc='d')

            h = -1 * matrix(b_ineq.astype(np.double), tc='d')
            solvers.options['show_progress'] = False
            sol = solvers.qp(P,q,G, h, verbose=False) # get dictionary for solution

            optimized_u = sol['x']

        else:
            optimized_u = self.compute_nom_control()


        return optimized_u

    def compute_nom_control(self, Kn=np.array([-0.08, -0.2])):
        #! mock
        vd = Kn[0]*(np.atleast_2d(self.state["x"][:2]).T - self.goal)
        u_nom = Kn[1]*(np.atleast_2d(self.state["xdot"][:2]).T - vd)

        if np.linalg.norm(u_nom) > 0.01:
            u_nom = (u_nom/np.linalg.norm(u_nom))* 0.01
        return u_nom.astype(np.double)


@np.vectorize
def h_func(r1, r2, a, b, safety_dist):
    hr = np.power(r1,4)/np.power(a, 4) + \
        np.power(r2, 4)/np.power(b, 4) - safety_dist
    return hr


def robot_step(state, state_hist, dyn, ecbf, new_obs):
    u_hat_acc = ecbf.compute_safe_control(obs=new_obs)
    u_hat_acc = np.ndarray.flatten(np.array(np.vstack((u_hat_acc,np.zeros((1,1))))))  # acceleration
    assert(u_hat_acc.shape == (3,))
    u_motor = go_to_acceleration(state, u_hat_acc, dyn.param_dict) # desired motor rate ^2

    state = dyn.step_dynamics(state, u_motor)
    ecbf.state = state
    state_hist.append(state["x"])
    return u_hat_acc

def plot_step(ecbf, new_obs, u_hat_acc, state_hist):
    state_hist_plot = np.array(state_hist)
    nom_cont = ecbf.compute_nom_control()
    multiplier_const = 100
    plt.plot([state_hist_plot[-1, 0], state_hist_plot[-1, 0] + multiplier_const *
                u_hat_acc[0]],
             [state_hist_plot[-1, 1], state_hist_plot[-1, 1] + multiplier_const * u_hat_acc[1]], color='r', linewidth=2, label="Safe Control")
    plt.plot([state_hist_plot[-1, 0], state_hist_plot[-1, 0] + multiplier_const *
                nom_cont[0]],
                [state_hist_plot[-1, 1], state_hist_plot[-1, 1] + multiplier_const * nom_cont[1]],color='b',linewidth=2,label="Nominal Control")

    plt.plot(state_hist_plot[:, 0], state_hist_plot[:, 1],'k')
    plt.plot(ecbf.goal[0], ecbf.goal[1], '*r')
    plt.plot(state_hist_plot[-1, 0], state_hist_plot[-1, 1], '8k') # current

    
    

def main():
    ### Initialize Robot 1 (state, dynamics, goal, ecbf control)
    state1 = {"x": np.array([1.5, -3.5, 10]),
                "xdot": np.zeros(3,),
                "theta": np.radians(np.array([0, 0, 0])),  
                "thetadot": np.radians(np.array([0, 0, 0]))  
                }
    dyn = QuadDynamics()
    goal1 = np.array([[-2.5], [0.75]])
    ecbf1 = ECBF_control(state1, goal1)

    ## Save robot position history for plotting and analysis
    state1_hist = []
    state1_hist.append(state1["x"])

    new_obs1 = np.array([[0], [0]]) # center of obstacle

    # ### Initialize Robot 2 (state, dynamics, goal, ecbf control)
    # state2 = {"x": np.array([-5, 3, 10]),
    #             "xdot": np.zeros(3,),
    #             "theta": np.radians(np.array([0, 0, 0])),  # ! hardcoded
    #             "thetadot": np.radians(np.array([0, 0, 0]))  # ! hardcoded
    #             }
    # dyn = QuadDynamics()
    # goal2 = np.array([[4], [-6]])
    # ecbf2 = ECBF_control(state2, goal2)
    # ## Save robot position history for plotting and analysis
    # state2_hist = []
    # state2_hist.append(state2["x"])

    # new_obs2 = np.array([[1], [1]])
    for tt in range(20000): # update ECBF obstacle with other robot position
        # new_obs1 = state2["x"][:2].reshape(2,1)
        # new_obs2 = state1["x"][:2].reshape(2,1)
        # print(new_obs1.shape)
        u_hat_acc1 = robot_step(state1, state1_hist, dyn, ecbf1, new_obs1)
        # u_hat_acc2 = robot_step(state2, state2_hist, dyn, ecbf2, new_obs2)

        if(tt % 25 == 0):
            print("Timestep", tt)
            plt.cla()
            start_t = time.time()

            plot_step(ecbf1, new_obs1, u_hat_acc1, state1_hist)
            # plot_step(ecbf2, new_obs2, u_hat_acc2, state2_hist)

            p1 = ecbf1.compute_plot_z(new_obs1)
            # p2 = ecbf1.compute_plot_z(new_obs2)
            x = p1["x"]
            y = p1["y"]
            z = p1["z"]
            # x = (p1["x"] + p2["x"]) / 2
            # y = (p1["y"] + p2["y"]) / 2
            # z = (p1["z"] + p2["z"]) / 2
            ecbf1.plot_h(x, y, z)









if __name__=="__main__":
    main()
