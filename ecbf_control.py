from dynamics import QuadDynamics
from controller import *
import numpy as np
import matplotlib.pyplot as plt
from cvxopt import matrix
from cvxopt import solvers
from matplotlib.patches import Ellipse

a = 1
b = 1
safety_dist = 2
class SimpleDynamics():
    def __init__(self):
        ## State space
        r = np.array([np.array([1,-4])]).T # position
        rd = np.array([np.array([0, 0])]).T  # velocity
        self.state = {"r":r, "rd":rd}
        ## Params
        self.dt = 10e-3

        # self.u = zeros(2,1) # acceleration, control input

    def step(self, u):
        # rdd = self.u
        rd = self.state["rd"] + self.dt * u - self.state["rd"] * 0.02
        r = self.state["r"] + self.dt * self.state["rd"]

        self.state["rd"] = rd
        self.state["r"]  = r

class ECBF_control():
    def __init__(self, state, goal=np.array([[0], [10]])):
        self.state = state
        self.shape_dict = {} #TODO: a, b
        # self.gain_dict = {} #TODO: Kp, Kd
        Kp = 6
        Kd = 8
        self.K = np.array([Kp, Kd])
        self.goal=goal
        self.use_safe = True
        # pass

    def compute_plot_z(self, obs):
        # obs = np.array([0,1]) #! mock
    
        plot_x = np.arange(-10, 10, 0.1)
        plot_y = np.arange(-10, 10, 0.1)
        xx, yy = np.meshgrid(plot_x, plot_y, sparse=True)
        z = np.zeros(xx.shape)
        for i in range(obs.shape[1]):
            ztemp = h_func(xx - obs[0][i], yy - obs[1][i], a, b, safety_dist) > 0
            # print("z temp size = "+str(ztemp.shape))
            z = z + ztemp
        z = z / (obs.shape[1]-1)
        p = {"x":plot_x, "y":plot_y, "z":z}
        return p
        
        # plt.show()
    def plot_h(self, plot_x, plot_y, z):
        h = plt.contourf(plot_x, plot_y, z, [-1, 0, 1],colors=['#808080', '#A0A0A0', '#C0C0C0'])
        # h = plt.contourf(plot_x, plot_y, z)
        plt.xlabel("X")
        plt.ylabel("Y")
        proxy = [plt.Rectangle((0, 0), 1, 1, fc=pc.get_facecolor()[0])
                 for pc in h.collections]
        # plt.legend(proxy, ["Unsafe: range(-1 to 0)","Safe: range(0 to 1)"])
        plt.legend()
        plt.pause(0.00000001)



    def compute_h(self, obs=np.array([[0], [0]]).T):
        h = np.zeros((obs.shape[1], 1))
        for i in range(obs.shape[1]):
            rel_r = np.atleast_2d(self.state["x"][:2]).T - obs[:, i].reshape(2,1)
            # TODO: a, safety_dist, obs, b
            hr = h_func(rel_r[0], rel_r[1], a, b, safety_dist)
            h[i] = hr
        return h

    def compute_hd(self, obs, obs_v):
        hd = np.zeros((obs.shape[1], 1))
        for i in range(obs.shape[1]):
            rel_r = np.atleast_2d(self.state["x"][:2]).T - obs[:, i].reshape(2,1)
            rd = np.atleast_2d(self.state["xdot"][:2]).T - obs_v[:, i].reshape(2,1)
            term1 = (4 * np.power(rel_r[0],3) * rd[0])/(np.power(a,4))
            term2 = (4 * np.power(rel_r[1],3) * rd[1])/(np.power(b,4))
            hd[i] = term1 + term2
        return hd

    def compute_A(self, obs):
        A = np.empty((0,2))
        for i in range(obs.shape[1]):
            rel_r = np.atleast_2d(self.state["x"][:2]).T - obs[:, i].reshape(2,1)
            A0 = (4 * np.power(rel_r[0], 3))/(np.power(a, 4))
            A1 = (4 * np.power(rel_r[1], 3))/(np.power(b, 4))
            Atemp = np.array([np.hstack((A0, A1))])
            
            A = np.array(np.vstack((A, Atemp)))
        
        
        return A

    def compute_h_hd(self, obs, obs_v):
        h = self.compute_h(obs)
        hd = self.compute_hd(obs, obs_v)
        # print("h = "+str(h.shape))
        # print("hd = "+str(hd.shape))
        # print("hhd = "+str(np.vstack((h, hd)).astype(np.double).shape))
        return np.vstack((h, hd)).astype(np.double)

    def compute_b(self, obs, obs_v):
        """extra + K * [h hd]"""
        # b = np.empty((0,1))
        # for i in range(obs.shape[1]):
        #     rel_r = np.atleast_2d(self.state["x"][:2]).T - obs[:, i].reshape(2,1)
        #     rd = np.atleast_2d(self.state["xdot"][:2]).T - obs_v[:, i].reshape(2,1)

        #     extra = -( (12 * np.square(rel_r[0]) * np.square(rd[0]))/np.power(a, 4) + (12 * np.square(rel_r[1]) * np.square(rd[1]))/np.power(b, 4) )

        #     b_ineq = extra - self.K @ self.compute_h_hd(obs)
        #     b = np.array(np.vstack((b, b_ineq)))

        #     print("b_ineq.shape = "+str(extra))

        rel_r = np.atleast_2d(self.state["x"][:2]).T - obs
        rd = np.atleast_2d(self.state["xdot"][:2]).T - obs_v

        extra = -( (12 * np.square(rel_r[0]) * np.square(rd[0]))/np.power(a, 4) + (12 * np.square(rel_r[1]) * np.square(rd[1]))/np.power(b, 4) )
        extra = extra.reshape(obs.shape[1], 1)

        # print("obs size = "+str(obs.shape))
        # print("self.compute_h_hd(obs, obs_v) = "+str(self.compute_h_hd(obs, obs_v).shape))
        b_ineq =  extra - ( self.K[0] * self.compute_h(obs) + self.K[1] * self.compute_hd(obs, obs_v) )
        # print("b_ineq = "+str(b_ineq.shape))

        
        return b_ineq



    def compute_safe_control(self,obs, obs_v):
        if self.use_safe:
            A = self.compute_A(obs)
            # assert(A.shape == (1,2))
            # print("A = "+str(A.shape))

            b_ineq = self.compute_b(obs, obs_v)
            # print("b = "+str(b_ineq.shape))
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
        # u = np.linalg.pinv(A) @ b_ineq

        # return u

    def compute_nom_control(self, Kn=np.array([-0.08, -0.2])):
        #! mock
        vd = Kn[0]*(np.atleast_2d(self.state["x"][:2]).T - self.goal)
        u_nom = Kn[1]*(np.atleast_2d(self.state["xdot"][:2]).T - vd)

        if np.linalg.norm(u_nom) > 0.01:
            u_nom = (u_nom/np.linalg.norm(u_nom))* 0.01
        return u_nom.astype(np.double)

    # def compute_control(self, obs):

class Robot_Sim():
    def __init__(self, x_init, goal_init, robot_id):
        self.id = robot_id
        self.state = {"x": x_init,
                "xdot": np.zeros(3,),
                "theta": np.radians(np.array([0, 0, 0])),  # ! hardcoded
                "thetadot": np.radians(np.array([0, 0, 0]))  # ! hardcoded
                }
        self.dyn = QuadDynamics()
        self.goal = goal_init
        self.ecbf = ECBF_control(self.state, self.goal)


        self.state_hist = []
        self.state_hist.append(self.state["x"])

        self.new_obs = np.array([[1], [1]])
    def robot_step(self, new_obs, obs_v):
        u_hat_acc = self.ecbf.compute_safe_control(obs=new_obs, obs_v=obs_v)
        u_hat_acc = np.ndarray.flatten(np.array(np.vstack((u_hat_acc,np.zeros((1,1))))))  # acceleration
        assert(u_hat_acc.shape == (3,))
        u_motor = go_to_acceleration(self.state, u_hat_acc, self.dyn.param_dict) # desired motor rate ^2

        self.state = self.dyn.step_dynamics(self.state, u_motor)
        self.ecbf.state = self.state
        self.state_hist.append(self.state["x"])
        return u_hat_acc

    def update_obstacles(self, robots, obs):
        obst = []
        obs_v = []
        for obj in robots:
            if obj.id == self.id:
                continue
            obst.append(obj.state["x"][:2].reshape(2,1))
            obs_v.append(obj.state["xdot"][:2].reshape(2,1))
        if not len(obs):
            return {"obs":obst, "obs_v":obs_v}
        for i in range(obs.shape[1]):
            obst.append(obs[i].reshape(2,1))
            obs_v.append(np.array([[0], [0]]))
        
        obstacles = {"obs":obst, "obs_v":obs_v}
        return obstacles
        



@np.vectorize
def h_func(r1, r2, a, b, safety_dist):
    hr = np.power(r1,4)/np.power(a, 4) + \
        np.power(r2, 4)/np.power(b, 4) - safety_dist
    return hr


# def robot_step(state, state_hist, dyn, ecbf, new_obs, obs_v):
#     u_hat_acc = ecbf.compute_safe_control(obs=new_obs, obs_v=obs_v)
#     u_hat_acc = np.ndarray.flatten(np.array(np.vstack((u_hat_acc,np.zeros((1,1))))))  # acceleration
#     assert(u_hat_acc.shape == (3,))
#     u_motor = go_to_acceleration(state, u_hat_acc, dyn.param_dict) # desired motor rate ^2

#     state = dyn.step_dynamics(state, u_motor)
#     ecbf.state = state
#     state_hist.append(state["x"])
#     return u_hat_acc

def plot_step(ecbf, new_obs, u_hat_acc, state_hist, plot_handle):
    state_hist_plot = np.array(state_hist)
    nom_cont = ecbf.compute_nom_control()
    multiplier_const = 100
    plot_handle.plot([state_hist_plot[-1, 0], state_hist_plot[-1, 0] + multiplier_const *
                u_hat_acc[0]],
                [state_hist_plot[-1, 1], state_hist_plot[-1, 1] + multiplier_const * u_hat_acc[1]], label="Safe")
    plot_handle.plot([state_hist_plot[-1, 0], state_hist_plot[-1, 0] + multiplier_const *
                nom_cont[0]],
                [state_hist_plot[-1, 1], state_hist_plot[-1, 1] + multiplier_const * nom_cont[1]],label="Nominal")

    plot_handle.plot(state_hist_plot[:, 0], state_hist_plot[:, 1],'k')
    plot_handle.plot(ecbf.goal[0], ecbf.goal[1], '*r')
    plot_handle.plot(state_hist_plot[-1, 0], state_hist_plot[-1, 1], '8k') # current
    print("plot obs shape = "+str(new_obs.shape[1]))
    for i in range(new_obs.shape[1]):
        print("plot obs no "+str(i)+" = ( x = "+str(new_obs[0, i])+", y = "+str(new_obs[1, i]))
        plot_handle.plot(new_obs[0, i], new_obs[1, i], '8k') # obs
    

    ell = Ellipse((state_hist_plot[-1, 0], state_hist_plot[-1, 1]), a*safety_dist+0.5, b*safety_dist+0.5, 0)
    ell.set_alpha(0.3)
    ell.set_facecolor(np.array([1, 0, 0]))
    
    plot_handle.add_artist(ell)
    
# def update_obstacles(robots, obs):
#     for obj in Robots:
#         new_obs1 = Robots[1].state["x"][:2].reshape(2,1)
    # new_obs1 = np.hstack((new_obs1, const_obs))
    # new_obs1 = np.hstack((new_obs1, const_obs2))
    # new_obs2 = Robots[0].state["x"][:2].reshape(2,1)
    # new_obs2 = np.hstack((new_obs2, const_obs))
    # new_obs2 = np.hstack((new_obs2, const_obs2))

    # obs_v1 = Robots[1].state["xdot"][:2].reshape(2,1)
    # obs_v1 = np.hstack((obs_v1, const_obs_v))
    # obs_v1 = np.hstack((obs_v1, const_obs_v2))

    # obs_v2 = Robots[0].state["xdot"][:2].reshape(2,1)
    # obs_v2 = np.hstack((obs_v2, const_obs_v))
    # obs_v2 = np.hstack((obs_v2, const_obs_v2))

def main():
    # pass
    # dyn = SimpleDynamics()
    
    ### Robot 1
    x_init1 = np.array([3, -5, 10])
    goal_init1 =np.array([[-6], [4]])
    Robot1 = Robot_Sim(x_init1, goal_init1, 0)

    ### Robot 2

    x_init2 =np.array([-5, 3, 10])
    goal_init2 =np.array([[4], [-6]])
    Robot2 = Robot_Sim(x_init2, goal_init2, 1)


    ### Robot 3

    x_init3 =np.array([-5, -3, 10])
    goal_init3 =np.array([[6], [4]])
    Robot3 = Robot_Sim(x_init3, goal_init3, 2)
    
    Robots = [Robot1, Robot2, Robot3]

    plt.plot([2, 2, 3])

    a, ax1 = plt.subplots()
    
    const_obs = np.array([[1], [1]])
    const_obs2 = np.array([[-2], [-2]])

    obs = np.hstack((const_obs2, const_obs)).T
    # obs = []

    

    # b, ax2 = plt.subplots()
    for tt in range(20000):

        obstacles = []
        
        for obj in Robots:
            obstacles.append(obj.update_obstacles(Robots, obs))
        # print("obs = "+str(new_obs1))
        # print("obs.shape = "+str(new_obs1.shape))
        # print("obs.shape = "+str(np.array(obstacles[0]["obs"])[:, :, 0].T.shape))
        # print(new_obs1.shape)
        u_hat_acc = []
        cnt = 0
        
        for obj in Robots:
            u_hat_acc.append(obj.robot_step(np.array(obstacles[cnt]["obs"])[:, :, 0].T, np.array(obstacles[cnt]["obs_v"])[:, :, 0].T))
            cnt = cnt + 1
        # u_hat_acc2 = Robots[1].robot_step(new_obs2, obs_v2)

        # obs = np.hstack((obs_v1, obs_v2, obs_v2))
        

        
        if(tt % 20 == 0):
            print(tt)
            plt.cla()
            cnt = 0
            p = []
            x = 0
            y = 0
            z = 0
            for obj in Robots:
                plot_step(obj.ecbf, np.array(obstacles[cnt]["obs"])[:, :, 0].T, u_hat_acc[cnt], obj.state_hist, ax1)
                # plot_step(Robots[1].ecbf, new_obs2, u_hat_acc2, Robots[1].state_hist, ax1)

                p.append( obj.ecbf.compute_plot_z(np.array(obstacles[cnt]["obs"])[:, :, 0].T) )
                # p2 = Robots[1].ecbf.compute_plot_z(new_obs2)
                # x = (p[0]["x"] + p[1]["x"]) / 2
                # y = (p[0]["y"] + p[1]["y"]) / 2
                # z = (p[0]["z"] + p[1]["z"]) / 2

                x = x + p[cnt]["x"]
                y = y + p[cnt]["y"]
                z = z + p[cnt]["z"]
                
                cnt = cnt + 1
            # ax2.plot(p1["x"], p1["y"])
            Robot2.ecbf.plot_h(x/cnt, y/cnt, z/cnt)
            plt.pause(0.00000001)
        



if __name__=="__main__":
    main()