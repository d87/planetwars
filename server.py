#!/usr/bin/env python

import subprocess
import time
import os
import math

MAX_TURNS = 200

class Planet(object):
    def __init__(self, id, x, y, growth_rate, owner, num_ships):
        self.id = id
        self.x = x
        self.y = y
        self.growth_rate = growth_rate
        self.owner = owner
        self.num_ships = num_ships
        self.arrived_fleets = []

    def __repr__(self):
        owner = self.owner and self.owner.id or 0
        return "P %d %f %f %d %d %d" % (self.id, self.x, self.y, self.growth_rate, owner, self.num_ships)

class Fleet(object):
    def __init__(self, src_planet, dst_planet, num_ships, owner, remaining_turns):
        self.src = src_planet
        self.dst = dst_planet
        self.num_ships = num_ships
        self.owner = owner 
        self.remaining_turns = remaining_turns



class PlayerResponse(object):
    def __init__(self, player):
        self.player = player
        self.fleetcmds = []
        self._finished = False
        self.outmessage = None

    def make_fleet(self, src,dst,num):
        self.fleetcmds.append((src,dst,num))




class Player(object):
    __counter = 0
    def __init__(self, cmdstring, team, name=None):
        process = subprocess.Popen(cmdstring, stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines = True)
        self.process = process

        self._eliminated = False

        Player.__counter += 1
        self.id = Player.__counter

        self.team = team
        self.name = name or "Player %d" % self.id

        #message to be sent with the state
        self.inbox = None


        self.response = PlayerResponse(self)

    def __repr__(self):
        return "<%s>" % self.name

    def send(self,s):
        self.process.stdin.write(s)

    def poll(self):
        if self.response._finished:
            #new turn, new response
            self.response = PlayerResponse(self)

        try:
            line = self.process.stdout.readline()
            if len(line) < 2:
                raise EOFError

            if line.startswith("."):
                self.response._finished = True
                # print("%s responded" % self.name)
                return True
            else:
                la = line.split()
                cmd = la[0]
                if cmd == "F":
                    srcPlanetID = int(la[1])
                    dstPlanetID = int(la[2])
                    num_ships = int(la[3])

                    self.response.make_fleet(srcPlanetID, dstPlanetID, num_ships)

                elif cmd == "M":
                    msg = int(la[1])
                    self.response.outmessage = msg

        except EOFError:
            return False



def proximity(planet1, planet2):
    return math.ceil(math.sqrt((planet2.x - planet1.x)**2 + (planet2.y - planet1.y)**2))

class Game(object):
    def __init__(self, player_list):
        self.turn_count = 0
        self.fleets = []
        self.planets = {}
        self.players = {}
        self.teams = {
            1 : [],
            2 : [] 
        }



        self.prepare_map(len(player_list))

        for player in player_list:
            #also assigns initial planets
            self.add_player(player)


    def kill_subprocs(self):
        for id,player in self.players.items():
            player.process.kill()

    def send_state(self, player):
        for id, planet in self.planets.items():
            player.send("%r\r\n" % planet) #repr

        if player.inbox != None: #no size check
            player.send("M %d\r\n" % player.inbox)
            player.inbox = None

        player.send("Y %d\r\n" % player.id)

    def add_player(self, player):
        for id, planet in self.planets.items():
            if planet.owner == 0:
                planet.owner = player
                break


        self.teams[player.team].append(player)

        playerID = player.id
        self.players[playerID] = player

    def get_next_player_on_team(self,player):
        """Returns next sibling in a circle"""
        team = self.teams[player.team]
        if len(team) < 2:
            return None
        i = 0
        while i < len(team):
            if team[i] == player:
                next_i = (i+1 < len(team)) and i+1 or 0
                return team[next_i]
            i+=1


    # def get_player(self, playerID):
        # return self.players[playerID]

    def planet_growth(self):
        for id, planet in self.planets.items():
            planet.num_ships += planet.growth_rate

    def elimination_check(self):
        """Winning condition checks"""
        for id, player in self.players.items():
            if player._eliminated:
                continue
            owned = 0
            for pid, planet in self.planets.items():
                if planet.owner == player:
                    owned +=1

            if owned == 0:
                player._eliminated = True
                # team = self.teams[player.team]
                # team.remove(player)
                print("!!! Eliminating", player.name)

        t1 = sum(not x._eliminated for x in self.teams[1])
        t2 = sum(not x._eliminated for x in self.teams[2])
        # print(t1,t2)
        if t1 == 0 and t2 > 0:
            return 2
        if t2 == 0 and t1 > 0:
            return 1
        if t1 == 0 and t2 == 0:
            return -1

    def advance_fleets(self):
        i = 0
        while i < len(self.fleets):
            fleet = self.fleets[i]
            fleet.remaining_turns -= 1
            if fleet.remaining_turns == 0:
                fleet.dst.arrived_fleets.append(fleet)
                self.fleets.pop(i)
            else:
                i+=1

    def fleet_vs_planet(self, fleet, planet):
        if planet.owner and fleet.owner in self.teams[planet.owner.team]:
            # merge allied fleets into planet force
            planet.num_ships += fleet.num_ships

        elif fleet.num_ships > planet.num_ships:
            #do battle, change owners
            prev_owner = planet.owner

            planet.owner = fleet.owner
            print("%r %s -> %s" % (planet, prev_owner, planet.owner))

            owner = fleet.owner

            planet.num_ships = fleet.num_ships - planet.num_ships
        else:
            planet.num_ships = planet.num_ships - fleet.num_ships

    def resolve_combat(self):
        for id, planet in self.planets.items():
            num_fleets = len(planet.arrived_fleets)
            if num_fleets > 0:
                if num_fleets == 1:
                    fleet = planet.arrived_fleets[0]
                    self.fleet_vs_planet(fleet, planet)
                else:
                    #merge all fleets from a single team under the strongest one
                    team1 = [f for f in planet.arrived_fleets if f.owner.team == 1]
                    if len(team1) != 0:
                        team1.sort(key=lambda x: x.num_ships)
                        team1cpt = team1[0].owner
                        team1num = sum(x.num_ships for x in team1)
                    else:
                        team1cpt = None
                        team1num = 0

                    team2 = [f for f in planet.arrived_fleets if f.owner.team == 2]
                    if len(team2) != 0:
                        team2.sort(key=lambda x: x.num_ships)
                        team2cpt = team2[0].owner
                        team2num = sum(x.num_ships for x in team2)
                    else:
                        team2cpt = None
                        team2num = 0

                    if team1num == team2num:
                        pass
                    else:
                        winner = (team1num > team2num) and team1cpt or team2cpt
                        if winner:
                            winner_ship_remains = abs(team1num - team2num)
                            winner_fleet = Fleet(None, planet, winner_ship_remains, winner, 0)
                            self.fleet_vs_planet(winner_fleet, planet)

                #flush present fleets list
                planet.arrived_fleets = []


    def turn(self):
        if self.turn_count > 0: #skip on first turn and just send initial state
            self.advance_fleets()
            self.resolve_combat()
            self.planet_growth()
            winner = self.elimination_check()
            if winner:
                return winner

        #send state to players
        for id, player in self.players.items():
            self.send_state(player)


        #wait until all players respond
        poll_list =  [p for pid, p in self.players.items()]
        while len(poll_list):
            time.sleep(0.001)
            i = 0
            while i < len(poll_list):
                player = poll_list[i]
                if player.poll():
                    #received response
                    poll_list.pop(i)
                else:
                    i+=1

        #modify game state from responses
        for id, player in self.players.items():
            for srcID,dstID,num in player.response.fleetcmds:
                srcPlanet = self.planets[srcID]
                dstPlanet = self.planets[dstID]
                srcPlanet.num_ships -= num
                newfleet = Fleet(srcPlanet, dstPlanet, num, player, proximity(srcPlanet, dstPlanet))
                self.fleets.append(newfleet)

            if player.response.outmessage != None:
                next = self.get_next_player_on_team(player)
                if next:
                    next.inbox = player.response.outmessage

        return 0



    def team_score(self, teamID):
        team = self.teams[teamID]
        score = 0

        for id, planet in self.planets.items():
            if planet.owner in team:
                score += planet.num_ships

        for fleet in self.fleets:
            if fleet.owner in team:
                score += fleet.num_ships
        return score

    def run(self):
        while self.turn_count < MAX_TURNS:
            winner = self.turn()
            if winner > 0:
                print("Winner is Team %s" % winner)
                for player in self.teams[winner]:
                    print(">", player.name)
                return
            elif winner < 0:
                print("Draw")
                return
            self.turn_count +=1

        #turn limit reached

        ts1 = self.team_score(1)
        ts2 = self.team_score(2)

        print("Team 1 Score: %d" % ts1)
        print("Team 2 Score: %d" % ts2)
        if ts1 > ts2:
            print("Winner is Team 1")
        if ts1 < ts2:
            print("Winner is Team 2")
        if ts1 == ts2:
            print("Draw")

    def prepare_map(self, player_count):
        f = open('map.txt', 'r')
        for line in f:
            pl = line.split()
            planetID = int(pl[1])
            x = float(pl[2])
            y = float(pl[3])
            growth_rate = int(pl[4])
            owner = int(pl[5])
            num_ships = int(pl[6])

            p = Planet(planetID, x, y, growth_rate, 0, num_ships)
            self.planets[planetID] = p



def main():
    try:
        bot1cmd = ["python", "bot.py"]
        bot2cmd = ["python", "bot.py"]
        g = Game([
            Player(bot1cmd, team=1, name="Oingo"),
            Player(bot1cmd, team=1, name="Boingo"),
            Player(bot1cmd, team=1, name="Yoyoma"),
            Player(bot2cmd, team=2, name="Johnny Joestar"),
            Player(bot2cmd, team=2, name="Gyro Zeppeli"),
            Player(bot2cmd, team=2, name="Lucy Steel"),
        ])
        g.run()
    except KeyboardInterrupt:
        exit(1)
    finally:
        g.kill_subprocs()


if __name__ == "__main__":
    main()
    