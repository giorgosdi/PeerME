import boto3
import ConfigParser
from os.path import expanduser
import argparse
import time

class VPCPeering(object):

    home = expanduser('~')
    aws_config_parser = ConfigParser.ConfigParser()
    aws_config_file = "{}/.aws/config".format(home)
    aws_config_file_path = expanduser(aws_config_file)
    aws_config_parser.read([aws_config_file_path])



    def __init__(self, master_profile_account, slave_profile_account, **vpc_ids):
        master_profile_sts_session = boto3.Session(profile_name="{}".format(master_profile_account))
        slave_profile_sts_session = boto3.Session(profile_name="{}".format(slave_profile_account))

        self.master_profile_sts = master_profile_sts_session.client('sts')
        self.slave_profile_sts = slave_profile_sts_session.client('sts')

        self.master_profile_section = 'profile {}'.format(master_profile_account)
        self.slave_profile_section = 'profile {}'.format(slave_profile_account)

        if vpc_ids:
            if vpc_ids.get('master_acc_vpc_id'):
                self.master_account_vpc_id = vpc_ids.get('master_acc_vpc_id')
                print self.master_account_vpc_id
            if vpc_ids.get('slave_acc_vpc_id'):
                self.slave_account_vpc_id = vpc_ids.get('slave_acc_vpc_id')
                print self.slave_account_vpc_id

    def create_routes(self, temporary_user, private_route_table_ids, vpc_cidr, vpc_peering_connections):
        try:
            if vpc_peering_connections:
                for vpc_peering_connection in vpc_peering_connections:
                    for route_table_id in private_route_table_ids:
                        print route_table_id
                        temporary_user.create_route(
                            DestinationCidrBlock=vpc_cidr,
                            RouteTableId=route_table_id,
                            VpcPeeringConnectionId=vpc_peering_connection['VpcPeeringConnectionId']
                        )
            else:
                print "."
                print "There are no pending peering connections"
        except Exception as error:
            print error

    def get_route_table_ids(self, temporary_user, vpc_id):
        try:
            private_route_table_ids = []
            filters=[
                {'Name': "vpc-id", "Values": [vpc_id]}
            ]

            route_tables = temporary_user.describe_route_tables(
                Filters=filters
            )['RouteTables']
            for route_table in route_tables:
                for tag in route_table['Tags']:
                    if 'private' in tag['Value']:
                        private_route_table_ids.append(route_table['RouteTableId'])

            return private_route_table_ids
        except Exception as error:
            print error

    def accept_vpc_peering(self, temporary_user, vpc_connections):
        try:
            if vpc_connections:
                for connection in vpc_connections:
                    temporary_user.accept_vpc_peering_connection(
                        VpcPeeringConnectionId=connection['VpcPeeringConnectionId']
                    )
            else:
                print "."
                print "No VPN connections found"
        except Exception as error:
            print error

    def get_peering_connections(self, temporary_user, state, existing_connections, master_vpc_id, slave_vpc_id=None):
        try:
            print "."
            print "Waiting for the peering connection to be available.."
            wait = True
            tries = 1
            while wait:
                filters=[
                    {'Name':'requester-vpc-info.vpc-id', 'Values':[master_vpc_id]},
                    {'Name': 'status-code', 'Values': [state]}
                ]
                if slave_vpc_id is not None:
                    filters.append({'Name': 'accepter-vpc-info.vpc-id', 'Values':[slave_vpc_id]})

                vpc_connections = temporary_user.describe_vpc_peering_connections(
                    Filters=filters
                )['VpcPeeringConnections']

                if vpc_connections:
                    wait=False
                else:
                    time.sleep(tries**2)
                    print "."
                    print "I will wait for {} second(s)".format(tries**2)
                    tries += 1

            if not wait:
                return vpc_connections
        except Exception as error:
            print error

    def vpc_peering(self, temporary_user, master_vpc_id, slave_vpc_id, slave_account_id):
        try:
            temporary_user.create_vpc_peering_connection(
                VpcId=master_vpc_id,
                PeerVpcId=slave_vpc_id,
                PeerOwnerId=slave_account_id
            )
        except Exception as error:
            print error
    def peering_connection_exists(self, temporary_user, master_vpc_id, slave_vpc_id):
        try:
            filters=[
                {'Name':'requester-vpc-info.vpc-id', 'Values':[master_vpc_id]},
                {'Name': 'accepter-vpc-info.vpc-id', 'Values':[slave_vpc_id]},
                {'Name': 'status-code', 'Values': ['active', 'pending-acceptance']}
            ]
            connection_id = temporary_user.describe_vpc_peering_connections(Filters = filters)['VpcPeeringConnections']
            if connection_ids:
                print "A VPC peering connection already exists for VPCs:"
                print master_vpc_id
                print slave_vpc_id
                print "The VPC connection Id is {}".format(connection_id)
        except Exception as error:
            print error

    def get_vpc_cidr(self, temporary_user, vpc_id):
        try:
            return temporary_user.describe_vpcs(VpcIds=[vpc_id])['Vpcs'][0]['CidrBlock']
        except Exception as error:
            print error

    def get_vpc_id(self, temporary_user):
        try:
            return temporary_user.describe_vpcs()['Vpcs'][0]['VpcId']
        except Exception as error:
            print error

    def create_temporary_user(self, sts_client, resource):
        try:
            temporary_user = boto3.client(
                resource,
                aws_access_key_id=sts_client['Credentials']['AccessKeyId'],
                aws_secret_access_key=sts_client['Credentials']['SecretAccessKey'],
                aws_session_token=sts_client['Credentials']['SessionToken'],
                region_name="eu-west-1"
            )
            return temporary_user
        except Exception as error:
            print error

    def assume_role(self, sts_client, account_number, role):
        try:
            return sts_client.assume_role(RoleArn='arn:aws:iam::{}:role/{}'.format(account_number, role), RoleSessionName="Temporary-{}".format(role) )
        except Exception as error:
            print error

    def get_profile_details_from_config(self):
        try:
            if self.aws_config_parser.has_section(self.master_profile_section):
                master_role_arn = self.aws_config_parser.get(self.master_profile_section, 'role_arn')
                master_account_number = master_role_arn.split(':')[4]
                master_account_role = master_role_arn.split(':')[5].split('/')[1]

            if self.aws_config_parser.has_section(self.slave_profile_section):
                slave_role_arn = self.aws_config_parser.get(self.slave_profile_section, 'role_arn')
                slave_account_number = slave_role_arn.split(':')[4]
                slave_account_role = slave_role_arn.split(':')[5].split('/')[1]

            return master_account_number, slave_account_number, master_account_role, slave_account_role, master_role_arn, slave_role_arn
        except Exception as error:
            print error

    def main_func(self, args):

        print ""
        print "Getting details from your config file.."
        master_account_number, slave_account_number, master_account_role, slave_account_role, master_role_arn, slave_role_arn = self.get_profile_details_from_config()

        print "."
        print "Assuming the roles from the provided profiles.."
        master_account_client = self.assume_role(self.master_profile_sts ,master_account_number, master_account_role)
        slave_account_client = self.assume_role(self.slave_profile_sts, slave_account_number, slave_account_role)

        print "."
        print "Creating temporary users from the assumed roles.."
        master_temporary_user = self.create_temporary_user(master_account_client, 'ec2')
        slave_temporary_user = self.create_temporary_user(slave_account_client, 'ec2')


        if args.multi_vpc:
            master_vpc_id = self.master_account_vpc_id
            slave_vpc_id = self.slave_account_vpc_id
        elif args.src_multi_vpc:
            master_vpc_id = self.master_account_vpc_id
            slave_vpc_id = self.get_vpc_id(slave_temporary_user)
        elif args.dest_multi_vpc:
            master_vpc_id = self.get_vpc_id(master_temporary_user)
            slave_vpc_id = self.slave_account_vpc_id
        else:
            master_vpc_id = self.get_vpc_id(master_temporary_user)
            slave_vpc_id = self.get_vpc_id(slave_temporary_user)

        try:
            print master_vpc_id, slave_vpc_id
            print "."
            print "VPC peering in progress.."
            self.vpc_peering(master_temporary_user, master_vpc_id, slave_vpc_id, slave_account_number)
            print "."
            print "VPCs peered successfully !"
            print "."
            print "Moving on to accept the connection"
            print "."
            print "Getting master account peering connections"
            master_peering_connections = self.get_peering_connections(master_temporary_user, 'pending-acceptance', [], master_vpc_id, slave_vpc_id)
            try:
                print "."
                print "Getting slave account peering connections"
                if args.accept_conns:
                    slave_peering_connections = self.get_peering_connections(slave_temporary_user, 'pending-acceptance', master_peering_connections, master_vpc_id)
                    if master_peering_connections:
                        if slave_peering_connections:
                            self.accept_vpc_peering(slave_temporary_user, slave_peering_connections)
                            print "."
                            print "All pending peer connections have been accepted !"
                else:
                    slave_peering_connections = self.get_peering_connections(slave_temporary_user, 'pending-acceptance', master_peering_connections, master_vpc_id, slave_vpc_id)
                    self.accept_vpc_peering(slave_temporary_user, slave_peering_connections)
                    print "."
                    print "The pending peering connection has been accepted !"


                if args.route_tables:
                    print "."
                    print "You chose to create the routes.."
                    master_route_table_ids = self.get_route_table_ids(master_temporary_user, master_vpc_id)
                    slave_route_table_ids = self.get_route_table_ids(slave_temporary_user, slave_vpc_id)
                    print "."
                    print "Creating routes.."
                    if master_route_table_ids:
                        slave_vpc_cidr = self.get_vpc_cidr(slave_temporary_user, slave_vpc_id)
                        self.create_routes(master_temporary_user, master_route_table_ids, slave_vpc_cidr, master_peering_connections)
                        print "."
                        print "Routes created in the master account.."
                    if slave_route_table_ids:
                        master_vpc_cidr = self.get_vpc_cidr(master_temporary_user, master_vpc_id)
                        self.create_routes(slave_temporary_user, slave_route_table_ids, master_vpc_cidr, slave_peering_connections)
                        print "."
                        print "Routes created in the slave account.."
            except Exception as error:
                print error
        except Exception as error:
            print error


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="VPC peering made simple")
    parser.add_argument("-mt", "--multi-vpc", action="store_true", help="If the both accounts have multiple VPCs, this flag should be raised", required=False, default=False)
    parser.add_argument("-d", "--dest-multi-vpc", action="store_true", help="If the destination account has multiple VPCs, this flag should be raised", required=False, default=False)
    parser.add_argument("-s", "--src-multi-vpc",  action="store_true", help="If the source account has multiple VPCs, this flag should be raised", required=False, default=False)
    parser.add_argument("-rt", "--route-tables",  action="store_true", help="Create routes for the peering connections", required=False, default=False)
    parser.add_argument("-ac", "--accept-conns", action="store_true", help="Accept all pending VPC peering connections on the target account", required=False, default=False)

    args = parser.parse_args()

    master_account_profile = raw_input('Provide the account you want to start the peering from : ')
    slave_account_profile = raw_input('Provide the account you want to peer : ')

    if args.multi_vpc:
        master_account_vpc_id = raw_input('Provide the VPC id you want to peer from : ')
        slave_account_vpc_id = raw_input('Provide the VPC id you want to peer : ')
        peerme = VPCPeering(master_account_profile, slave_account_profile, master_acc_vpc_id=master_account_vpc_id, slave_acc_vpc_id=slave_account_vpc_id)
    elif args.dest_multi_vpc:
        slave_account_vpc_id = raw_input('Provide the VPC id you want to peer : ')
        peerme = VPCPeering(master_account_profile, slave_account_profile, slave_acc_vpc_id=slave_account_vpc_id)
    elif args.src_multi_vpc:
        master_account_vpc_id = raw_input('Provide the VPC id you want to peer from : ')
        peerme = VPCPeering(master_account_profile, slave_account_profile, master_acc_vpc_id=master_account_vpc_id)
    else:
        peerme = VPCPeering(master_account_profile, slave_account_profile)

    peerme.main_func(args)


